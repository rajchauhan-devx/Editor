from project_safety import write_json
import os
import sys
import json
import subprocess
import re
from typing import Dict, Any, List

# Locate FFmpeg binary
FFMPEG_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "AIGamingEditor", "tools", "ffmpeg", "bin", "ffmpeg.exe"
)
if not os.path.exists(FFMPEG_PATH):
    try:
        import imageio_ffmpeg
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = "ffmpeg"

def run_ffmpeg(args: List[str], timeout: int = 7200) -> subprocess.CompletedProcess:
    """Run FFmpeg command line synchronously."""
    cmd = [FFMPEG_PATH] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and args != ["-i", args[-1]]:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-2000:]}")
    return result

def inspect_media(file_path: str) -> Dict[str, Any]:
    """Inspect video file metadata using FFmpeg stderr header analysis."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    res = run_ffmpeg(["-i", file_path], timeout=15)
    output = res.stderr

    # 1. Parse Duration
    duration_sec = 0.0
    duration_str = "00:00:00"
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
    if dur_match:
        hours, mins, secs = dur_match.groups()
        duration_sec = int(hours) * 3600 + int(mins) * 60 + float(secs)
        duration_str = f"{int(hours):02d}:{int(mins):02d}:{int(float(secs)):02d}"

    # 2. Parse Video Stream (resolution, fps, codec)
    resolution = "Unknown"
    fps = 0
    v_codec = "Unknown"
    video_match = re.search(r"Stream #0:\d+.*?: Video: ([^,\s]+).*?, (\d+x\d+).*?, (\d+(?:\.\d+)?) (?:fps|tbr)", output)
    if video_match:
        v_codec = video_match.group(1)
        resolution = video_match.group(2)
        fps = round(float(video_match.group(3)))
    else:
        res_match = re.search(r", (\d{3,4}x\d{3,4})", output)
        if res_match:
            resolution = res_match.group(1)
        fps_match = re.search(r", (\d+(?:\.\d+)?) fps", output)
        if fps_match:
            fps = round(float(fps_match.group(1)))

    # 3. Parse All Audio Streams
    audio_tracks = []
    # Match any Stream #0:X: Audio: ...
    stream_lines = [line.strip() for line in output.split("\n") if "Stream #0:" in line and "Audio:" in line]
    
    track_idx = 1
    for line in stream_lines:
        stream_id_match = re.search(r"Stream #0:(\d+)", line)
        stream_id = int(stream_id_match.group(1)) if stream_id_match else track_idx
        
        codec_match = re.search(r"Audio:\s*([^,\s]+)", line)
        codec = codec_match.group(1) if codec_match else "aac"
        
        hz_match = re.search(r"(\d+)\s*Hz", line)
        rate = int(hz_match.group(1)) if hz_match else 48000
        
        is_mono = "mono" in line.lower()
        channels = 1 if is_mono else 2

        # Intelligent OBS Track Classification
        track_role = "game"
        if is_mono:
            track_role = "mic"
        elif track_idx == 1:
            track_role = "backup"
        elif track_idx == 2:
            track_role = "game"
        elif track_idx == 3:
            track_role = "mic"

        audio_tracks.append({
            "id": track_idx,
            "stream_index": stream_id,
            "name": f"Track {track_idx}: {'Microphone (Mono)' if track_role == 'mic' else 'Game Audio (Stereo)' if track_role == 'game' else 'Backup Master Mix'} ({codec})",
            "type": track_role,
            "channels": channels,
            "sample_rate": rate,
            "codec": codec,
        })
        track_idx += 1

    if duration_sec <= 0 or resolution == "Unknown" or fps <= 0:
        raise ValueError("Could not inspect video duration, resolution or frame rate")

    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = round(file_size_bytes / (1024 * 1024), 1)

    # Pick smart defaults
    game_tr = next((t["id"] for t in audio_tracks if t["type"] == "game"), 1)
    mic_tr = next((t["id"] for t in audio_tracks if t["type"] == "mic"), 2 if len(audio_tracks) > 1 else 1)

    return {
        "file_name": os.path.basename(file_path),
        "file_path": os.path.abspath(file_path),
        "file_size_mb": file_size_mb,
        "duration_seconds": duration_sec,
        "duration_formatted": duration_str,
        "resolution": resolution,
        "fps": fps,
        "video_codec": v_codec,
        "audio_tracks": audio_tracks,
        "total_audio_tracks": len(audio_tracks),
        "suggested_mapping": {
            "game_track": game_tr,
            "mic_track": mic_tr,
            "backup_track": 1
        }
    }

def extract_audio_streams(file_path: str, output_dir: str, game_track: int = 2, mic_track: int = 3) -> Dict[str, str]:
    """Extract game audio and microphone tracks into separate cached WAV files."""
    metadata = inspect_media(file_path)
    tracks = {track["id"] for track in metadata["audio_tracks"]}
    if not tracks:
        raise ValueError("No audio tracks found in the media file")
    if game_track not in tracks or mic_track not in tracks:
        raise ValueError(f"Selected audio track(s) not found in file (tracks available: {sorted(list(tracks))})")
    os.makedirs(output_dir, exist_ok=True)
    game_wav = os.path.join(output_dir, "game_audio.wav")
    mic_wav = os.path.join(output_dir, "mic_audio.wav")

    game_stream = max(0, game_track - 1)
    mic_stream = max(0, mic_track - 1)

    # 1. Extract Game Audio (Stereo 48kHz for high fidelity)
    run_ffmpeg([
        "-y", "-i", file_path,
        "-map", f"0:a:{game_stream}",
        "-ac", "2", "-ar", "48000",
        game_wav
    ], timeout=7200)

    # 2. Extract Microphone Audio (16kHz Mono for Whisper and Silero VAD)
    run_ffmpeg([
        "-y", "-i", file_path,
        "-map", f"0:a:{mic_stream}",
        "-ac", "1", "-ar", "16000",
        mic_wav
    ], timeout=7200)

    return {
        "game_audio_path": os.path.abspath(game_wav),
        "mic_audio_path": os.path.abspath(mic_wav)
    }

def generate_ai_proxy(file_path: str, output_proxy_path: str, target_height: int = 720) -> Dict[str, Any]:
    """
    Generate lightweight 720p 30fps AI proxy for Gemini full-session analysis.
    Uses fast CPU/GPU encoding, keeping the master 1080p60 untouched.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_proxy_path)), exist_ok=True)

    cmd = [
        "-y", "-i", file_path,
        "-vf", f"scale=-2:{target_height}",
        "-r", "30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        output_proxy_path
    ]

    run_ffmpeg(cmd, timeout=14400)
    proxy_size_mb = round(os.path.getsize(output_proxy_path) / (1024 * 1024), 1) if os.path.exists(output_proxy_path) else 0

    return {
        "proxy_path": os.path.abspath(output_proxy_path),
        "proxy_size_mb": proxy_size_mb,
        "status": "ready"
    }
