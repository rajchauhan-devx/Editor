from project_safety import write_json
import os
import sys
import gc
import json
import wave
import subprocess
from typing import Dict, Any, List, Optional
import pyttsx3
import media_engine
from project_safety import identifier

def get_audio_duration_sec(wav_path: str) -> float:
    """Measure exact duration of a WAV file in seconds."""
    if not os.path.exists(wav_path):
        return 0.0
    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return round(frames / float(rate), 3)
    except Exception:
        return 0.0

def list_available_voices() -> List[Dict[str, Any]]:
    """List local TTS voices available on Windows."""
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    results = []
    for i, v in enumerate(voices):
        results.append({
            "id": v.id,
            "index": i,
            "name": v.name,
            "languages": v.languages if hasattr(v, "languages") else ["en"],
            "gender": "Female" if "zira" in v.name.lower() or "female" in v.name.lower() else "Male",
            "gaming_preset": f"Gaming {'Female' if 'zira' in v.name.lower() else 'Male'} {i+1:02d}"
        })
    del engine
    gc.collect()
    return results

def synthesize_dialogue_line(
    text: str,
    output_path: str,
    target_duration_sec: float = 2.4,
    voice_index: int = 0,
    match_timing: bool = True
) -> Dict[str, Any]:
    """
    Synthesizes a single English gamer reaction line with timing slot alignment.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_raw = output_path + ".raw.wav"

    # 1. Initialize local TTS engine
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    if not voices or not 0 <= voice_index < len(voices):
        raise ValueError("Selected system voice is unavailable")
    if voices:
        engine.setProperty("voice", voices[voice_index].id)
    
    # Fast energetic gamer speech rate (175 - 190 wpm)
    engine.setProperty("rate", 180)
    engine.save_to_file(text, temp_raw)
    engine.runAndWait()
    del engine
    gc.collect()

    raw_duration = get_audio_duration_sec(temp_raw)
    if raw_duration <= 0:
        raise RuntimeError("TTS did not produce a valid voice clip")
    final_duration = raw_duration

    # 2. Timing Slot Alignment: Adjust atempo via FFmpeg if necessary
    if match_timing and target_duration_sec > 0.5 and raw_duration > 0.3:
        tempo_ratio = raw_duration / target_duration_sec
        # Cap tempo adjustment between 0.8x and 1.35x to avoid audio distortion
        tempo_clamped = max(0.8, min(1.35, tempo_ratio))

        if abs(tempo_clamped - 1.0) > 0.08:
            media_engine.run_ffmpeg([
                "-y", "-i", temp_raw,
                "-filter:a", f"atempo={tempo_clamped:.2f}",
                output_path
            ], timeout=30)
            final_duration = get_audio_duration_sec(output_path)
            try:
                os.remove(temp_raw)
            except Exception:
                pass
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_raw, output_path)
    else:
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(temp_raw, output_path)

    if match_timing and final_duration > target_duration_sec + 0.15:
        raise ValueError("English voice exceeds its time slot. Shorten the rewrite and retry.")
    return {
        "output_path": os.path.abspath(output_path),
        "raw_duration_sec": raw_duration,
        "final_duration_sec": final_duration,
        "target_duration_sec": target_duration_sec,
        "sync_drift_ms": round((final_duration - target_duration_sec) * 1000)
    }

def generate_session_voice_dub(
    project_dir: str,
    voice_index: int = 0,
    match_timing: bool = True
) -> Dict[str, Any]:
    """
    Phase 4 Core Function:
    1. Reads english_lines.json (Phase 3).
    2. Synthesizes each replacement line into voices/dlg-{id}.wav.
    3. Assembles continuous full-session replacement voice track (ai_voice_dub.wav).
    4. Saves voice_manifest.json.
    5. Updates media.json state to 'ready_for_master_render' (Phase 5).
    """
    english_lines_path = os.path.join(project_dir, "english_lines.json")
    media_json_path = os.path.join(project_dir, "media.json")

    if not os.path.exists(english_lines_path):
        raise FileNotFoundError(f"english_lines.json not found in {project_dir}. Run Phase 3 Director first.")

    with open(english_lines_path, "r", encoding="utf-8") as f:
        english_lines = json.load(f)

    with open(media_json_path, "r", encoding="utf-8") as f:
        media_data = json.load(f)

    # Old exports and cache receipts no longer describe a regenerated dub.
    for artifact in ("voice_manifest.json", "render_manifest.json", "voice_cache.json"):
        filename = os.path.join(project_dir, artifact)
        if os.path.isfile(filename):
            os.remove(filename)

    total_duration_sec = media_data.get("original_master", {}).get("duration_seconds", 30.0)

    voices_dir = os.path.join(project_dir, "voices")
    os.makedirs(voices_dir, exist_ok=True)

    synthesized_clips = []
    print(f"[TTS WORKER] Synthesizing {len(english_lines)} English gamer dubbing lines...")

    for line in english_lines:
        line_id = identifier(line["line_id"])
        text = line["english_rewrite"]
        target_slot = line.get("target_duration_sec", 2.4)
        out_wav = os.path.join(voices_dir, f"{line_id}.wav")

        synth_res = synthesize_dialogue_line(
            text=text,
            output_path=out_wav,
            target_duration_sec=target_slot,
            voice_index=voice_index,
            match_timing=match_timing
        )

        synthesized_clips.append({
            "line_id": line_id,
            "start_seconds": line.get("start_seconds", 0.0),
            "end_seconds": line.get("end_seconds", 2.5),
            "original_hindi": line.get("original_hindi", ""),
            "english_rewrite": text,
            "clip_path": synth_res["output_path"],
            "duration_sec": synth_res["final_duration_sec"]
        })

    # Assemble complete continuous replacement track aligned to session timeline
    combined_voice_track = os.path.join(project_dir, "ai_voice_dub.wav")
    
    # Generate continuous track using FFmpeg amix or adelay
    if synthesized_clips:
        # Build FFmpeg complex filter to delay and mix each line at its exact start timestamp
        inputs = []
        filter_delays = []
        for i, clip in enumerate(synthesized_clips):
            inputs.extend(["-i", clip["clip_path"]])
            delay_ms = int(clip["start_seconds"] * 1000)
            filter_delays.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
        
        mix_inputs = "".join(f"[a{i}]" for i in range(len(synthesized_clips)))
        filter_complex = f"{';'.join(filter_delays)};{mix_inputs}amix=inputs={len(synthesized_clips)}:normalize=0,apad[aout]"
        
        media_engine.run_ffmpeg(
            inputs + ["-filter_complex", filter_complex, "-map", "[aout]", "-t", str(total_duration_sec), "-y", combined_voice_track],
            timeout=120
        )
    else:
        # Generate silent track if no dialogue lines
        media_engine.run_ffmpeg([
            "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
            "-t", str(total_duration_sec), "-y", combined_voice_track
        ], timeout=60)

    # Save manifest
    manifest_path = os.path.join(project_dir, "voice_manifest.json")
    manifest_data = {
        "project_id": media_data.get("project_id"),
        "total_lines_synthesized": len(synthesized_clips),
        "combined_voice_track": os.path.abspath(combined_voice_track),
        "clips": synthesized_clips
    }

    write_json(manifest_path, manifest_data)

    # Update media.json status to Phase 4 Complete
    media_data["phase"] = 4
    media_data["status"] = "ready_for_master_render"
    media_data["voice_dub"] = {
        "track_path": os.path.abspath(combined_voice_track),
        "manifest_path": os.path.abspath(manifest_path),
        "total_lines": len(synthesized_clips)
    }

    write_json(media_json_path, media_data)

    print(f"[TTS WORKER] Phase 4 Complete. Created continuous voice track: {combined_voice_track}")

    return {
        "success": True,
        "total_clips": len(synthesized_clips),
        "combined_track": os.path.abspath(combined_voice_track),
        "manifest_path": os.path.abspath(manifest_path),
        "status": "ready_for_master_render"
    }
