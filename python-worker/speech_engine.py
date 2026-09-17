from project_safety import write_json
import os
import sys
import gc
import json
import math
import wave
import subprocess
import numpy as np
from typing import Dict, Any, List, Optional
from faster_whisper import WhisperModel
import media_engine

MODELS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "AIGamingEditor", "models"
)
os.makedirs(MODELS_DIR, exist_ok=True)

def load_audio_numpy(wav_path: str) -> np.ndarray:
    """
    Load a WAV audio file as a float32 numpy array normalized to [-1.0, 1.0].
    Ensures 16kHz mono using FFmpeg if not already converted.
    """
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    # Check sample rate using wave module
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_frames = wf.readframes(n_frames)

    # If it's already 16kHz mono 16-bit
    if n_channels == 1 and framerate == 16000 and sampwidth == 2:
        return np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0

    # Otherwise convert via FFmpeg to 16kHz mono PCM
    temp_wav = wav_path + ".16k.wav"
    media_engine.run_ffmpeg([
        "-y", "-i", wav_path,
        "-ac", "1", "-ar", "16000",
        temp_wav
    ], timeout=60)

    with wave.open(temp_wav, "rb") as wf:
        raw_frames = wf.readframes(wf.getnframes())
    
    try:
        os.remove(temp_wav)
    except Exception:
        pass

    return np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0

def estimate_voice_emotion(text: str) -> Dict[str, Any]:
    """
    Classify gamer reaction emotion and intensity from transcribed phrasing and punctuation.
    """
    text_lower = text.lower()
    emotion = "Calm"
    intensity = "medium"
    
    if "?" in text and any(w in text_lower for w in ["kaha", "where", "kyu", "why", "kaise", "how", "kya", "what"]):
        emotion = "Surprised"
        intensity = "high"
    elif "!" in text or any(w in text_lower for w in ["dude", "bhai", "omg", "look out", "run", "cover"]):
        emotion = "Excited"
        intensity = "high"
    elif any(w in text_lower for w in ["dhoka", "betray", "knew it", "bola tha", "maine"]):
        emotion = "Vindicated"
        intensity = "high"
    elif any(w in text_lower for w in ["haha", "lol", "yaar", "kidding", "pagal", "mar gaya"]):
        emotion = "Laughing"
        intensity = "medium"
    elif any(w in text_lower for w in ["ammo", "die", "dead", "gaya", "no way"]):
        emotion = "Surprised"
        intensity = "high"
    else:
        emotion = "Calm"
        intensity = "low"

    return {
        "emotion": emotion,
        "intensity": intensity
    }

def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def transcribe_audio_file(
    audio_path: str,
    output_dir: str,
    model_size: str = "base",
    language: Optional[str] = None
) -> Dict[str, Any]:
    """
    Phase 2 Core Worker:
    1. Load WAV into numpy array via standard library (immune to AppLocker DLL blocks).
    2. Load Whisper with Silero VAD.
    3. Transcribe speech with word-level timestamps.
    4. Auto-unload Whisper model immediately (RTX 3050 6GB Sequential Execution).
    5. Save transcript.json and emotion.json.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Load audio into numpy
    audio_np = load_audio_numpy(audio_path)
    audio_duration_sec = round(len(audio_np) / 16000.0, 2)
    print(f"[SPEECH WORKER] Audio loaded: {audio_duration_sec}s")

    # 2. Sequential GPU Loading: Load Whisper
    print(f"[SPEECH WORKER] Loading Whisper model ({model_size}) with Silero VAD...")
    try:
        model = WhisperModel(model_size, device="auto", compute_type="default", download_root=MODELS_DIR)
    except Exception:
        print(f"[SPEECH WORKER] Auto load failed, using tiny model...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8", download_root=MODELS_DIR)

    # 3. Transcribe with Silero VAD active
    print(f"[SPEECH WORKER] Transcribing with Silero VAD enabled...")
    try:
        segments_generator, info = model.transcribe(
            audio_np,
            language=language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
            beam_size=5
        )
        detected_language = info.language or "hi"
        lang_probability = round(info.language_probability, 3) if info.language_probability else 0.0
        raw_segments = list(segments_generator)
    finally:
        del model
        gc.collect()

    dialogue_lines = []
    emotions = []
    line_idx = 1

    for seg in raw_segments:
        text = seg.text.strip()
        if not text:
            continue

        start_sec = round(seg.start, 2)
        end_sec = round(seg.end, 2)
        duration_slot = round(end_sec - start_sec, 2)

        emo_data = estimate_voice_emotion(text)

        dialogue_item = {
            "id": f"dlg-{line_idx}",
            "index": line_idx,
            "timestamp": format_timestamp(start_sec),
            "start_seconds": start_sec,
            "end_seconds": end_sec,
            "target_duration_sec": duration_slot,
            "original_text": text,
            "confidence": round(math.exp(seg.avg_logprob), 3),
            "emotion": emo_data["emotion"],
            "intensity": emo_data["intensity"],
            "keep_scene": True,
            "subtitle": True
        }

        dialogue_lines.append(dialogue_item)
        emotions.append({
            "line_id": f"dlg-{line_idx}",
            "timestamp": format_timestamp(start_sec),
            "emotion": emo_data["emotion"],
            "intensity": emo_data["intensity"],
        })
        line_idx += 1

    # 5. Save persistent outputs
    transcript_path = os.path.join(output_dir, "transcript.json")
    emotion_path = os.path.join(output_dir, "emotion.json")

    transcript_payload = {
        "audio_source": os.path.basename(audio_path),
        "detected_language": detected_language,
        "language_confidence": lang_probability,
        "total_speech_segments": len(dialogue_lines),
        "dialogue_lines": dialogue_lines
    }

    write_json(transcript_path, transcript_payload)

    write_json(emotion_path, emotions)

    print(f"[SPEECH WORKER] Complete. Saved {len(dialogue_lines)} lines to {transcript_path}")

    return {
        "status": "ready_for_director_analysis",
        "detected_language": detected_language,
        "language_confidence": lang_probability,
        "total_segments": len(dialogue_lines),
        "transcript_path": os.path.abspath(transcript_path),
        "emotion_path": os.path.abspath(emotion_path),
        "lines": dialogue_lines
    }
