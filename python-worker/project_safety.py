"""Validation and atomic persistence shared by the local workers."""
import json
import math
import os
import re
import tempfile
from pathlib import Path


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", value):
        raise ValueError("Invalid project or dialogue identifier")
    return value


def contained_path(root, *parts):
    base = Path(root).resolve()
    result = base.joinpath(*parts).resolve()
    if not result.is_relative_to(base) or result == base:
        raise ValueError("Path must remain inside the project directory")
    return str(result)


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_director(output, transcript, duration):
    """Fail closed on hallucinated lines, invalid time spans or unsupported effects."""
    if not isinstance(output, dict):
        raise ValueError("Director output must be an object")
    segments = output.get("story_segments")
    lines = output.get("english_lines")
    if not isinstance(segments, list) or not segments or not isinstance(lines, list):
        raise ValueError("Director must return story segments and English lines")
    def interval(item):
        start, end = item.get("start_seconds"), item.get("end_seconds")
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in (start, end)):
            raise ValueError("Invalid timeline numbers")
        if not 0 <= start < end <= duration + 0.05:
            raise ValueError("Timeline interval outside the original recording")
        return start, end
    cursor = 0.0
    for seg in segments:
        start, end = interval(seg)
        if abs(start - cursor) > 0.05:
            raise ValueError("Story map must cover the recording without gaps or overlaps")
        if seg.get("action") not in ("keep", "cut", "compress", "protect_keep"):
            raise ValueError("Unsupported edit action")
        if seg.get("protected_story") or seg.get("event") in ("cutscene", "dialogue"):
            seg.update(action="protect_keep", protected_story=True)
        cursor = end
    if abs(cursor - duration) > 0.05:
        raise ValueError("Story map does not cover the full recording")
    originals = {line["id"]: line for line in transcript.get("dialogue_lines", [])}
    seen = set()
    for line in lines:
        key = identifier(line.get("line_id"))
        if key in seen or key not in originals:
            raise ValueError("Director invented or duplicated a dialogue line")
        seen.add(key)
        original = originals[key]
        # The worker owns timing. A model cannot move reactions into another scene.
        line.update(start_seconds=original["start_seconds"], end_seconds=original["end_seconds"],
                    timestamp=original["timestamp"], original_hindi=original["original_text"],
                    target_duration_sec=original["end_seconds"] - original["start_seconds"])
        start, end = interval(line)
        if not isinstance(line.get("english_rewrite"), str) or not line["english_rewrite"].strip():
            raise ValueError("Empty English rewrite")
        # Effects are unavailable until an asset-backed renderer is implemented.
        line.update(zoom=1.0, sfx=None, meme=None)
        for seg in segments:
            if start < seg["end_seconds"] and end > seg["start_seconds"]:
                seg["action"] = "protect_keep" if seg.get("protected_story") else "keep"
    if seen != set(originals):
        raise ValueError("Director omitted transcript lines")
    return output
