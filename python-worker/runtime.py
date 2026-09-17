"""Serialized worker execution and persistent, resumable pipeline jobs."""
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager, nullcontext
from project_safety import write_json

WORKER_LOCK = threading.Lock()


@contextmanager
def worker_slot():
    if not WORKER_LOCK.acquire(blocking=False):
        raise RuntimeError("Another media/AI worker is active. Wait for it to finish.")
    try:
        yield
    finally:
        WORKER_LOCK.release()


def source_signature(path):
    stat = os.stat(path)
    return {"path": os.path.realpath(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def run_pipeline(project_dir, api_key, model, voice_index, lock_reserved=False):
    import speech_engine
    import gemini_director
    import tts_engine
    job_path = os.path.join(project_dir, "pipeline.json")
    def state(status, stage, error=None):
        write_json(job_path, {"status": status, "stage": stage, "error": error, "updated_at": time.time()})
    def cached_stage(name, inputs, outputs, operation):
        fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        receipt = os.path.join(project_dir, f"{name}_cache.json")
        try:
            with open(receipt, encoding="utf-8") as stream:
                old = json.load(stream)
            if old["fingerprint"] == fingerprint and all(os.path.isfile(os.path.join(project_dir, p)) for p in outputs):
                return
        except (OSError, ValueError, KeyError):
            pass
        state("running", name)
        operation()
        write_json(receipt, {"fingerprint": fingerprint})
    def contents(name):
        with open(os.path.join(project_dir, name), encoding="utf-8") as stream:
            return json.load(stream)
    try:
        with (nullcontext() if lock_reserved else worker_slot()):
            media = contents("media.json")
            original = media["original_master"]["file_path"]
            if media.get("source_signature") != source_signature(original):
                raise ValueError("Original recording changed since import. Create a new project.")
            mic = os.path.join(project_dir, "mic_audio.wav")
            cached_stage("transcript", source_signature(mic), ["transcript.json", "emotion.json"],
                lambda: speech_engine.transcribe_audio_file(mic, project_dir, model_size="base"))
            cached_stage("director", {"transcript": contents("transcript.json"), "proxy": source_signature(os.path.join(project_dir, "ai_proxy.mp4")), "model": model},
                ["story_map.json", "english_lines.json", "edit_plan.json"],
                lambda: gemini_director.analyze_session_with_gemini(project_dir, api_key, model_name=model))
            cached_stage("voice", {"lines": contents("english_lines.json"), "voice": voice_index}, ["voice_manifest.json", "ai_voice_dub.wav"],
                lambda: tts_engine.generate_session_voice_dub(project_dir, voice_index))
        state("completed", "Ready to Export")
    except Exception as exc:
        # Credentials must never appear in job logs.
        message = str(exc).replace(api_key, "[redacted]") if api_key else str(exc)
        state("error", "Pipeline stopped", message)
    finally:
        if lock_reserved:
            WORKER_LOCK.release()
