"""Deterministic cut/compress mapping shared by video, game audio, dub and subtitles."""
import copy
import math


def compile_timeline(segments, duration):
    cursor = 0.0
    output_cursor = 0.0
    result = []
    for segment in segments:
        start, end = segment["start_seconds"], segment["end_seconds"]
        if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in (start, end)):
            raise ValueError("Invalid timeline timestamp")
        if abs(start - cursor) > 0.05 or not 0 <= start < end <= duration + 0.05:
            raise ValueError("Edit plan must cover the source in order without gaps or overlaps")
        action = segment.get("action")
        if action not in ("keep", "protect_keep", "cut", "compress"):
            raise ValueError("Unsupported timeline action")
        if segment.get("protected_story") and action in ("cut", "compress"):
            raise ValueError("Cannot cut or compress a protected scene")
        if action != "cut":
            speed = 4.0 if action == "compress" else 1.0
            length = (end - start) / speed
            result.append({"start": start, "end": end, "speed": speed, "output_start": output_cursor, "output_end": output_cursor + length})
            output_cursor += length
        cursor = end
    if abs(cursor - duration) > 0.05 or not result:
        raise ValueError("Edit plan must retain footage and cover the entire source")
    return result, output_cursor


def remap_dialogue(lines, timeline):
    result = []
    for original in lines:
        start, end = original["start_seconds"], original["end_seconds"]
        overlaps = [s for s in timeline if start < s["end"] and end > s["start"]]
        covered = sum(min(end, s["end"]) - max(start, s["start"]) for s in overlaps)
        if not overlaps or covered < end - start - 0.01 or any(s["speed"] != 1 for s in overlaps):
            raise ValueError("A cut or compression overlaps a voice line. Restore that segment first.")
        line = copy.deepcopy(original)
        line["start_seconds"] = overlaps[0]["output_start"] + start - overlaps[0]["start"]
        line["end_seconds"] = overlaps[-1]["output_start"] + end - overlaps[-1]["start"]
        result.append(line)
    return result


def timeline_filter(timeline):
    count = len(timeline)
    filters = []
    for source, prefix, splitter in [("0:v", "v", "split"), ("1:a", "g", "asplit"), ("2:a", "d", "asplit")]:
        filters.append(f"[{source}]{splitter}={count}" + ''.join(f"[{prefix}{i}]" for i in range(count)))
    concat_inputs = []
    for i, segment in enumerate(timeline):
        start, end, speed = segment["start"], segment["end"], segment["speed"]
        filters.append(f"[v{i}]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{speed}[vt{i}]")
        for prefix in ("g", "d"):
            tempo = ",atempo=2,atempo=2" if speed == 4 else ""
            filters.append(f"[{prefix}{i}]atrim=start={start}:end={end},asetpts=PTS-STARTPTS{tempo}[{prefix}t{i}]")
        concat_inputs.append(f"[vt{i}][gt{i}][dt{i}]")
    filters.append(''.join(concat_inputs) + f"concat=n={count}:v=1:a=2[edited_video][edited_game][edited_voice]")
    return ';'.join(filters)
