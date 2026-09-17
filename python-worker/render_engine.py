from project_safety import write_json
"""
AI Gaming Editor - Master Video Render Engine (Phase 5)
Hardware-accelerated master video export using NVIDIA NVENC / MediaFoundation,
multi-track audio ducking, styled gaming subtitles, and live FFmpeg progress parsing.
"""

import os
import sys
import re
import json
import time
import subprocess
import threading
from typing import Optional, Callable, Dict, Any

import media_engine
from project_safety import contained_path
from timeline_engine import compile_timeline, remap_dialogue, timeline_filter
from runtime import source_signature

FFMPEG_PATH = media_engine.FFMPEG_PATH

def probe_best_video_encoder() -> Dict[str, Any]:
    """
    Detect the fastest available hardware video encoder on this Windows system.
    Priority:
    1. NVIDIA NVENC (h264_nvenc) - dedicated RTX/GTX silicon encoder
    2. Windows MediaFoundation (h264_mf) - hardware acceleration via OS MFT
    3. CPU Software (libx264) - universal fallback
    """
    test_file = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "AIGamingEditor", "projects", "_probe_test.mp4"
    )
    os.makedirs(os.path.dirname(test_file), exist_ok=True)

    candidates = [
        {"codec": "h264_nvenc", "args": ["-c:v", "h264_nvenc", "-preset", "p5"], "desc": "NVIDIA NVENC Hardware (RTX/GTX)", "is_hw": True},
        {"codec": "h264_mf", "args": ["-c:v", "h264_mf"], "desc": "Windows MediaFoundation Hardware", "is_hw": True},
        {"codec": "libx264", "args": ["-c:v", "libx264", "-preset", "veryfast"], "desc": "CPU Software (x264)", "is_hw": False},
    ]

    for candidate in candidates:
        cmd = [
            FFMPEG_PATH, "-y", "-nostdin",
            "-f", "lavfi", "-i", "testsrc=duration=0.2:size=320x240:rate=30",
            *candidate["args"],
            "-frames:v", "5",
            test_file
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            if res.returncode == 0 and os.path.exists(test_file) and os.path.getsize(test_file) > 500:
                try:
                    os.remove(test_file)
                except Exception:
                    pass
                return candidate
        except Exception:
            pass
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception:
                    pass

    raise RuntimeError("No working H.264 encoder found")

def generate_ass_subtitles(dialogue_lines: list, output_path: str, width: int = 1920, height: int = 1080) -> str:
    """
    Generate Advanced SubStation Alpha (.ass) subtitles with YouTube gaming aesthetics:
    Impact / Arial Black font, bold yellow text with thick black outline.
    """
    def format_ass_time(seconds: float) -> str:
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            centis = 99
        return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

    font_size = int(round(height * 0.042))
    margin_v = int(round(height * 0.08))

    ass_content = f"""[Script Info]
Title: AI Gaming Editor Dub
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: GamerSub,Arial Black,{font_size},&H0000E5FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    for line in dialogue_lines:
        start_sec = line.get("start_seconds", 0.0)
        end_sec = line.get("end_seconds", start_sec + line.get("target_duration_sec", 2.0))
        text = line.get("english_rewrite") or line.get("text") or line.get("original_text", "")
        text = text.replace("\\", " ").replace("\r", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()
        start_str = format_ass_time(start_sec)
        end_str = format_ass_time(end_sec)
        ass_content += f"Dialogue: 0,{start_str},{end_str},GamerSub,,0,0,0,,{text}\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return output_path

def render_master_video(
    project_dir: str,
    preset: str = "YouTube 1440p60",
    encoder_choice: Optional[str] = None,
    output_filename: Optional[str] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Execute Phase 5 Master Video Render:
    1. Read project metadata & immutable master recording
    2. Read clean game_audio.wav + synthesized ai_voice_dub.wav
    3. Generate stylized subtitle track (.ass)
    4. Construct FFmpeg filtergraph (audio ducking + video resolution scale + subtitle burn)
    5. Encode master video using hardware acceleration with real-time frame progress streaming
    """
    media_json_path = os.path.join(project_dir, "media.json")
    if not os.path.exists(media_json_path):
        raise FileNotFoundError(f"Project media.json not found in {project_dir}")

    with open(media_json_path, "r", encoding="utf-8") as f:
        media_info = json.load(f)

    master_path = media_info.get("original_master", {}).get("file_path")
    if not master_path or not os.path.exists(master_path):
        raise FileNotFoundError(f"Original master recording file not found at: {master_path}")

    duration_sec = media_info.get("original_master", {}).get("duration_seconds", 5.0)
    master_fps = media_info.get("original_master", {}).get("fps", 60)
    total_expected_frames = int(round(duration_sec * master_fps))
    if total_expected_frames <= 0:
        total_expected_frames = 300

    # Audio sources
    game_audio_path = os.path.join(project_dir, "game_audio.wav")
    voice_dub_path = os.path.join(project_dir, "ai_voice_dub.wav")

    # Dialogue lines for subtitles
    english_lines_path = os.path.join(project_dir, "english_lines.json")
    dialogue_lines = []
    if os.path.exists(english_lines_path):
        try:
            with open(english_lines_path, "r", encoding="utf-8") as f:
                dialogue_lines = json.load(f)
        except Exception:
            pass

    if media_info.get("source_signature") != source_signature(master_path):
        raise ValueError("Original recording changed since import")
    with open(os.path.join(project_dir, "edit_plan.json"), encoding="utf-8") as stream:
        plan = json.load(stream)
    timeline, duration_sec = compile_timeline(plan.get("story_map", []), duration_sec)
    dialogue_lines = remap_dialogue(dialogue_lines, timeline)

    # Preset settings
    preset_configs = {
        "YouTube 1440p60": {"width": 2560, "height": 1440, "fps": 60, "bitrate": "24M"},
        "YouTube 1080p60": {"width": 1920, "height": 1080, "fps": 60, "bitrate": "14M"},
        "YouTube 4K60": {"width": 3840, "height": 2160, "fps": 60, "bitrate": "45M"},
        "TikTok / Shorts 1080x1920": {"width": 1080, "height": 1920, "fps": 60, "bitrate": "12M"},
    }
    if preset not in preset_configs:
        raise ValueError("Unsupported export preset")
    cfg = preset_configs[preset]
    total_expected_frames = int(round(duration_sec * cfg["fps"]))

    # Output file path
    proj_id = media_info.get("project_id", "project")
    if not output_filename:
        safe_preset = preset.split()[0].lower() + "_" + str(cfg["height"]) + "p"
        output_filename = f"{proj_id}_master_{safe_preset}.mp4"
    if os.path.basename(output_filename) != output_filename or not output_filename.lower().endswith(".mp4"):
        raise ValueError("Output must be an MP4 filename inside the project")
    output_path = contained_path(project_dir, output_filename)
    if os.path.normcase(os.path.realpath(output_path)) == os.path.normcase(os.path.realpath(master_path)):
        raise ValueError("Cannot overwrite the original recording")

    # Subtitle file
    ass_sub_path = os.path.join(project_dir, "master_subtitles.ass")
    subtitles_available = False
    if dialogue_lines:
        try:
            generate_ass_subtitles(dialogue_lines, ass_sub_path, width=cfg["width"], height=cfg["height"])
            subtitles_available = True
        except Exception as e:
            raise RuntimeError("Subtitle generation failed") from e

    # Determine Encoder
    if encoder_choice and "nvenc" in encoder_choice.lower():
        enc = probe_best_video_encoder()
        if not enc.get("is_hw") or "nvenc" not in enc.get("codec", ""):
            pass
        else:
            enc = {"codec": "h264_nvenc", "args": ["-c:v", "h264_nvenc", "-preset", "p5", "-b:v", cfg["bitrate"]], "desc": "NVIDIA NVENC Hardware (RTX)", "is_hw": True}
    else:
        enc = probe_best_video_encoder()

    # Video filter
    if "TikTok" in preset:
        v_filter = f"crop=ih*(9/16):ih,scale={cfg['width']}:{cfg['height']}:flags=lanczos,fps={cfg['fps']}"
    else:
        v_filter = f"scale={cfg['width']}:{cfg['height']}:flags=lanczos,fps={cfg['fps']}"

    if subtitles_available and os.path.exists(ass_sub_path):
        escaped_sub = ass_sub_path.replace("\\", "/").replace(":", "\\:")
        v_filter_with_subs = f"{v_filter},subtitles='{escaped_sub}'"
    else:
        v_filter_with_subs = v_filter

    has_game_audio = os.path.exists(game_audio_path)
    has_voice_dub = os.path.exists(voice_dub_path)

    if not has_game_audio or not has_voice_dub:
        raise FileNotFoundError("Separate game audio and a generated English dub are required")
    cmd = [FFMPEG_PATH, "-y", "-nostdin", "-i", master_path, "-i", game_audio_path, "-i", voice_dub_path]
    filter_complex_parts = [timeline_filter(timeline), f"[edited_video]{v_filter_with_subs}[vout]",
        "[edited_voice]asplit=2[voice_sc][voice_mix];"
        "[edited_game][voice_sc]sidechaincompress=threshold=0.08:ratio=4:attack=20:release=250[ducked_game];"
        "[ducked_game][voice_mix]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]"]
    audio_map = "[aout]"

    full_filter_complex = ";".join(filter_complex_parts)
    # Long sessions can exceed Windows' command-line length limit.
    filter_path = os.path.join(project_dir, "render_filters.txt")
    with open(filter_path, "w", encoding="utf-8") as stream:
        stream.write(full_filter_complex)

    cmd.extend([
        "-filter_complex_script", filter_path,
        "-map", "[vout]",
        "-map", audio_map,
        *enc["args"],
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-t", str(duration_sec),
        output_path + ".partial.mp4"
    ])

    print(f"[RENDER ENGINE] Starting render with {enc['desc']} -> {output_path}", flush=True)
    start_time = time.time()

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )

    # Concurrently drain stderr to prevent OS pipe buffer deadlock
    stderr_lines = []
    def drain_stderr():
        try:
            for s_line in iter(process.stderr.readline, ''):
                if s_line:
                    stderr_lines.append(s_line)
                    if len(stderr_lines) > 60:
                        stderr_lines.pop(0)
        except Exception:
            pass

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()

    last_frame = 0
    current_fps = 0.0

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break

        line = line.strip()
        if not line:
            continue

        if line.startswith("frame="):
            try:
                last_frame = int(line.split("=")[1].strip())
            except Exception:
                pass
        elif line.startswith("fps="):
            try:
                current_fps = float(line.split("=")[1].strip())
            except Exception:
                pass
        elif line.startswith("progress="):
            prog_val = line.split("=")[1].strip()
            percent = min(99.0, max(0.0, (last_frame / max(1, total_expected_frames)) * 100.0))
            if prog_val == "end":
                percent = 100.0

            elapsed = time.time() - start_time
            eta = ((elapsed / max(1, percent)) * (100.0 - percent)) if percent > 0 else 0.0

            if progress_callback:
                progress_callback({
                    "status": "rendering",
                    "percent": round(percent, 1),
                    "current_frame": last_frame,
                    "total_frames": total_expected_frames,
                    "fps": round(current_fps, 1),
                    "elapsed_sec": round(elapsed, 1),
                    "eta_sec": round(eta, 1),
                    "encoder": enc["desc"]
                })

    process.wait()
    stderr_thread.join(timeout=1)
    process.stdout.close()
    process.stderr.close()

    if process.returncode != 0:
        err_msg = "".join(stderr_lines[-20:])
        print(f"[RENDER ENGINE] Warning/Error from FFmpeg: {err_msg}", flush=True)
        raise RuntimeError(f"FFmpeg render failed: {err_msg[-2000:]}")

    partial_path = output_path + ".partial.mp4"
    if not os.path.exists(partial_path) or os.path.getsize(partial_path) < 1000:
        raise RuntimeError(f"Render completed but output file is missing or empty: {output_path}")

    os.replace(partial_path, output_path)
    total_time = time.time() - start_time
    file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)

    manifest = {
        "project_id": proj_id,
        "preset": preset,
        "resolution": f"{cfg['width']}x{cfg['height']}",
        "fps": cfg["fps"],
        "encoder": enc["desc"],
        "is_hardware_accelerated": enc["is_hw"],
        "render_time_sec": round(total_time, 2),
        "duration_seconds": duration_sec,
        "output_file": output_path,
        "file_size_mb": file_size_mb,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "ready"
    }

    manifest_path = os.path.join(project_dir, "render_manifest.json")
    write_json(manifest_path, manifest)

    if progress_callback:
        progress_callback({
            "status": "completed",
            "percent": 100.0,
            "current_frame": total_expected_frames,
            "total_frames": total_expected_frames,
            "fps": round(current_fps, 1),
            "elapsed_sec": round(total_time, 1),
            "eta_sec": 0.0,
            "output_path": output_path,
            "file_size_mb": file_size_mb,
            "encoder": enc["desc"]
        })

    return manifest
