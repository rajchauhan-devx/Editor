from project_safety import write_json
import os
import sys
import shutil
import platform
import subprocess
import json
import time
import threading
import importlib.util
import re
from functools import wraps
import secrets
import hmac
from project_safety import identifier, contained_path, write_json
from runtime import worker_slot, run_pipeline, source_signature, WORKER_LOCK
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import psutil
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import media_engine
import speech_engine
import gemini_director
import tts_engine
import render_engine

app = FastAPI(
    title="AI Gaming Editor - Local Worker Daemon",
    description="Deterministic local AI worker & hardware telemetry daemon for AI Gaming Editor",
    version="1.0.0"
)

# Enable CORS for local Electron & Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

PROJECTS_BASE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "AIGamingEditor", "projects"
)
os.makedirs(PROJECTS_BASE_DIR, exist_ok=True)
TOKEN_PATH = os.path.join(os.path.dirname(PROJECTS_BASE_DIR), "worker-token")
try:
    with open(TOKEN_PATH, "x", encoding="utf-8") as stream:
        stream.write(secrets.token_urlsafe(48))
except FileExistsError:
    pass
with open(TOKEN_PATH, encoding="utf-8") as stream:
    WORKER_TOKEN = stream.read().strip()
if not WORKER_TOKEN:
    raise RuntimeError("Worker token file is empty")

def project_path(project_id):
    try:
        return contained_path(PROJECTS_BASE_DIR, identifier(project_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.exception_handler(ValueError)
async def invalid_input(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.middleware("http")
async def guard_local_requests(request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in {"null", "http://localhost:5173", "http://127.0.0.1:5173"}:
        return JSONResponse(status_code=403, content={"detail": "Untrusted origin"})
    if request.method != "OPTIONS":
        token = request.headers.get("x-worker-token") or request.query_params.get("token", "")
        if not hmac.compare_digest(token, WORKER_TOKEN):
            return JSONResponse(status_code=401, content={"detail": "Local worker authentication required"})
    return await call_next(request)


def serialized(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            with worker_slot():
                return function(*args, **kwargs)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return wrapper

def get_gpu_info():
    """Probe GPU details using nvidia-smi if available, otherwise WMI / fallback."""
    gpu_data = {
        "name": "GPU unavailable",
        "load_percent": 0,
        "vram_used_mb": 0,
        "vram_total_mb": 0,
        "nvenc_supported": False,
        "source": "unavailable"
    }
    
    try:
        query = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
        res = subprocess.run(query, shell=True, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) >= 4:
                gpu_data["name"] = parts[0]
                gpu_data["load_percent"] = int(parts[1])
                gpu_data["vram_used_mb"] = int(parts[2])
                gpu_data["vram_total_mb"] = int(parts[3])
                gpu_data["source"] = "nvidia-smi"
                return gpu_data
    except Exception:
        pass

    if platform.system() == "Windows":
        try:
            wmic = subprocess.run(
                'powershell -Command "(Get-CimInstance Win32_VideoController).Name"',
                shell=True, capture_output=True, text=True, timeout=3
            )
            if wmic.returncode == 0 and wmic.stdout.strip():
                names = [n.strip() for n in wmic.stdout.strip().split("\n") if n.strip()]
                nv_names = [n for n in names if "NVIDIA" in n.upper() or "RTX" in n.upper()]
                if nv_names:
                    gpu_data["name"] = nv_names[0]
                    gpu_data["source"] = "wmi"
                elif names:
                    gpu_data["name"] = names[0]
                    gpu_data["source"] = "wmi"
        except Exception:
            pass

    return gpu_data

@app.get("/api/health")
def get_health():
    return {
        "status": "online",
        "service": "AI Gaming Editor Local Worker Daemon",
        "version": "1.0.0",
        "protocol_version": 2,
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "ffmpeg_installed": os.path.exists(media_engine.FFMPEG_PATH),
        "ffmpeg_path": media_engine.FFMPEG_PATH,
        "whisper_installed": importlib.util.find_spec("faster_whisper") is not None,
        "gemini_director_ready": bool(os.environ.get("GEMINI_API_KEY")),
        "tts_engine_ready": importlib.util.find_spec("pyttsx3") is not None
    }

@app.get("/api/system/status")
def get_system_status():
    gpu = get_gpu_info()
    current_drive = os.path.splitdrive(os.path.abspath("."))[0] or "C:"
    disk = psutil.disk_usage(PROJECTS_BASE_DIR)
    ram = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=None)

    return {
        "gpu": {
            "name": gpu["name"],
            "load_percent": gpu["load_percent"],
            "vram_used_mb": gpu["vram_used_mb"],
            "vram_total_mb": gpu["vram_total_mb"],
            "vram_percent": round((gpu["vram_used_mb"] / max(1, gpu["vram_total_mb"])) * 100, 1),
            "nvenc_supported": gpu["nvenc_supported"],
            "source": gpu["source"]
        },
        "cpu": {
            "load_percent": cpu_percent,
            "cores": psutil.cpu_count(logical=True)
        },
        "ram": {
            "used_gb": round((ram.total - ram.available) / (1024 ** 3), 2),
            "total_gb": round(ram.total / (1024 ** 3), 2),
            "percent": ram.percent
        },
        "disk": {
            "drive": current_drive,
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "percent_used": disk.percent
        },
        "active_worker": {
            "stage": "busy" if WORKER_LOCK.locked() else "idle",
            "active_model": None,
            "sequential_pipeline": "ready"
        }
    }

# --- REAL PROJECT DISCOVERY & SYSTEM ACTIVITY LOGS ---

@app.get("/api/projects")
def list_projects_endpoint():
    """Discover all real projects saved on local disk in PROJECTS_BASE_DIR."""
    projects_list = []
    if not os.path.exists(PROJECTS_BASE_DIR):
        return {"projects": []}

    for item in os.listdir(PROJECTS_BASE_DIR):
        pdir = os.path.join(PROJECTS_BASE_DIR, item)
        if not os.path.isdir(pdir):
            continue

        media_path = os.path.join(pdir, "media.json")
        if not os.path.exists(media_path):
            continue

        try:
            with open(media_path, "r", encoding="utf-8") as f:
                media_data = json.load(f)

            orig = media_data.get("original_master", {})
            p_id = media_data.get("project_id", item)
            p_name = media_data.get("project_name", item)

            has_render = os.path.exists(os.path.join(pdir, "render_manifest.json"))
            has_voice = os.path.exists(os.path.join(pdir, "voice_manifest.json"))
            has_edit_plan = os.path.exists(os.path.join(pdir, "edit_plan.json"))
            has_transcript = os.path.exists(os.path.join(pdir, "transcript.json"))

            if has_render:
                status = "Completed"
                task_desc = "Master video rendered"
                progress = 100
            elif has_voice:
                status = "Ready to Export"
                task_desc = "AI English voice dub synthesized & aligned"
                progress = 85
            elif has_edit_plan:
                status = "Plan Ready"
                task_desc = "Gemini Director edit plan & story map ready"
                progress = 65
            elif has_transcript:
                status = "Imported"
                task_desc = "Whisper transcription & Silero VAD complete"
                progress = 40
            else:
                status = "Imported"
                task_desc = "Media inspected & 720p AI proxy ready"
                progress = 20

            proxy_mb = media_data.get("ai_proxy", {}).get("proxy_size_mb", 0.0)

            raw_tracks = orig.get("audio_tracks", [])
            audio_tracks = []
            for t in raw_tracks:
                audio_tracks.append({
                    "id": t.get("id", 1),
                    "name": t.get("name", f"Track {t.get('id', 1)}"),
                    "type": t.get("type", "game"),
                    "channels": t.get("channels", 2)
                })

            projects_list.append({
                "id": p_id,
                "name": p_name,
                "game": media_data.get("game", "Gameplay"),
                "status": status,
                "duration": orig.get("duration_formatted", "Unknown"),
                "durationSeconds": orig.get("duration_seconds", 0),
                "sourceFile": orig.get("file_name", "Unknown"),
                "resolution": orig.get("resolution", "Unknown"),
                "fps": orig.get("fps", 0),
                "codec": orig.get("video_codec", "Unknown"),
                "audioTracks": audio_tracks,
                "progress": progress,
                "lastActive": "Active now" if has_render else "Recently updated",
                "costEstimate": 0,
                "costBudget": 0,
                "currentTask": task_desc,
                "proxySizeMb": proxy_mb,
            })
        except Exception as e:
            print(f"[PROJECT SCAN ERROR] {item}: {e}")

    return {"projects": projects_list}

@app.get("/api/media/proxy-video")
def get_proxy_video_endpoint(project_id: str = Query(...)):
    """Stream lightweight 720p AI proxy video for smooth timeline scrubbing."""
    proj_dir = project_path(project_id)
    proxy_path = os.path.join(proj_dir, "ai_proxy.mp4")
    if not os.path.exists(proxy_path):
        raise HTTPException(status_code=404, detail="Proxy video not found")
    return FileResponse(proxy_path, media_type="video/mp4")

@app.get("/api/system/activity-logs")
def get_activity_logs_endpoint(project_id: Optional[str] = None):
    """Return real chronological pipeline activity events from disk artifacts."""
    if not project_id:
        return {"logs": []}
    directory = project_path(project_id)
    logs = []
    for filename, sender in [("media.json", "Media"), ("transcript.json", "Speech worker"),
                             ("edit_plan.json", "Gemini"), ("voice_manifest.json", "Speech worker"),
                             ("render_manifest.json", "FFmpeg")]:
        path = os.path.join(directory, filename)
        if os.path.isfile(path):
            logs.append({"id": filename, "time": time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(path))),
                         "sender": sender, "message": f"Saved {filename}", "type": "success"})
    return {"logs": logs}

# --- PHASE 1: MEDIA INSPECTION & EXTRACTION ---

class InspectMediaRequest(BaseModel):
    file_path: str

@app.post("/api/media/inspect")
def inspect_media_endpoint(req: InspectMediaRequest):
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at: {req.file_path}")
    try:
        data = media_engine.inspect_media(req.file_path)
        return {"success": True, "media": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PrepareSessionRequest(BaseModel):
    file_path: str
    project_id: str
    project_name: str
    game_track: int = 2
    mic_track: int = 3

@app.post("/api/media/prepare-session")
@serialized
def prepare_session_endpoint(req: PrepareSessionRequest):
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="File not found")

    project_dir = project_path(req.project_id)
    if os.path.exists(project_dir):
        raise HTTPException(status_code=409, detail="Project already exists")
    os.makedirs(project_dir)

    metadata = media_engine.inspect_media(req.file_path)
    audio_paths = media_engine.extract_audio_streams(
        req.file_path, 
        project_dir, 
        game_track=req.game_track, 
        mic_track=req.mic_track
    )
    proxy_path = os.path.join(project_dir, "ai_proxy.mp4")
    proxy_info = media_engine.generate_ai_proxy(req.file_path, proxy_path, target_height=720)

    media_json_path = os.path.join(project_dir, "media.json")
    persistent_data = {
        "project_id": req.project_id,
        "project_name": req.project_name,
        "source_signature": source_signature(req.file_path),
        "original_master": metadata,
        "audio_separation": {
            "game_track_selected": req.game_track,
            "mic_track_selected": req.mic_track,
            "game_audio_path": audio_paths["game_audio_path"],
            "mic_audio_path": audio_paths["mic_audio_path"],
        },
        "ai_proxy": proxy_info,
        "phase": 1,
        "status": "ready_for_speech_analysis"
    }

    write_json(media_json_path, persistent_data)

    return {
        "success": True,
        "project_dir": project_dir,
        "media_json_path": media_json_path,
        "metadata": metadata,
        "audio_paths": audio_paths,
        "proxy": proxy_info
    }

# --- PHASE 2: SPEECH RECOGNITION & VAD ---

class TranscribeRequest(BaseModel):
    project_id: str
    model_size: str = "base"
    language: Optional[str] = None

@app.post("/api/speech/transcribe")
@serialized
def transcribe_speech_endpoint(req: TranscribeRequest):
    project_dir = project_path(req.project_id)
    mic_audio_path = os.path.join(project_dir, "mic_audio.wav")

    if not os.path.exists(mic_audio_path):
        raise HTTPException(status_code=404, detail=f"Extracted mic audio not found in {project_dir}")

    try:
        result = speech_engine.transcribe_audio_file(
            audio_path=mic_audio_path,
            output_dir=project_dir,
            model_size=req.model_size,
            language=req.language
        )

        media_json_path = os.path.join(project_dir, "media.json")
        if os.path.exists(media_json_path):
            with open(media_json_path, "r", encoding="utf-8") as f:
                pj_data = json.load(f)
            pj_data["phase"] = 2
            pj_data["status"] = "ready_for_director_analysis"
            pj_data["transcript_info"] = {
                "total_speech_segments": result["total_segments"],
                "detected_language": result["detected_language"],
                "transcript_path": result["transcript_path"],
                "emotion_path": result["emotion_path"],
            }
            write_json(media_json_path, pj_data)

        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- PHASE 3: GEMINI DIRECTOR REASONING & STORY MAPPING ---

class DirectorAnalyzeRequest(BaseModel):
    project_id: str
    api_key: Optional[str] = None
    mode: str = "Story"
    model_name: str = "gemini-2.5-flash"

@app.post("/api/director/analyze")
@serialized
def director_analyze_endpoint(req: DirectorAnalyzeRequest):
    project_dir = project_path(req.project_id)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project {req.project_id} directory not found")

    try:
        res = gemini_director.analyze_session_with_gemini(
            project_dir=project_dir,
            api_key=req.api_key,
            mode=req.mode,
            model_name=req.model_name
        )
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- PHASE 4: LOCAL ENGLISH VOICE SYNTHESIS (TTS) ---

@app.get("/api/voice/voices")
@serialized
def list_voices_endpoint():
    """List available local speech voices."""
    return {"voices": tts_engine.list_available_voices()}

class GenerateDubRequest(BaseModel):
    project_id: str
    voice_index: int = 0
    match_timing: bool = True

@app.post("/api/voice/generate-dub")
@serialized
def generate_dub_endpoint(req: GenerateDubRequest):
    """
    Phase 4 Core Endpoint:
    Synthesizes each English line from english_lines.json into voices/dlg-{id}.wav
    and assembles the continuous session replacement voice track ai_voice_dub.wav.
    """
    project_dir = project_path(req.project_id)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project {req.project_id} directory not found")

    try:
        res = tts_engine.generate_session_voice_dub(
            project_dir=project_dir,
            voice_index=req.voice_index,
            match_timing=req.match_timing
        )
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PreviewClipRequest(BaseModel):
    text: str
    target_duration_sec: float = 2.4
    voice_index: int = 0

@app.post("/api/voice/preview-clip")
@serialized
def preview_clip_endpoint(req: PreviewClipRequest):
    """Synthesize single line preview on-demand."""
    temp_preview = os.path.join(PROJECTS_BASE_DIR, "preview_temp.wav")
    try:
        res = tts_engine.synthesize_dialogue_line(
            text=req.text,
            output_path=temp_preview,
            target_duration_sec=req.target_duration_sec,
            voice_index=req.voice_index,
            match_timing=True
        )
        return {"success": True, "clip": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GeminiTestRequest(BaseModel):
    api_key: str

@app.post("/api/gemini/test-connection")
def test_gemini_connection(req: GeminiTestRequest):
    if not req.api_key or len(req.api_key) < 10:
        raise HTTPException(status_code=400, detail="Invalid API Key format")
    
    import urllib.request
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    try:
        req_obj = urllib.request.Request(url, headers={"x-goog-api-key": req.api_key}, method="GET")
        with urllib.request.urlopen(req_obj, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m["name"] for m in data.get("models", []) if "gemini" in m.get("name", "")]
                return {
                    "success": True,
                    "message": "Connected to Gemini API successfully",
                    "available_gemini_models_count": len(models)
                }
    except Exception as e:
        return {
            "success": False,
            "message": "Gemini connection failed. Check the key and network connection."
        }

# --- AUDIO PLAYBACK & STREAMING ROUTES ---

@app.get("/api/voice/play")
def play_dialogue_clip(project_id: str = Query(...), line_id: str = Query(...)):
    """Serve individual synthesized dialogue wav file for live UI audio playback."""
    clip_path = contained_path(project_path(project_id), "voices", f"{identifier(line_id)}.wav")
    if not os.path.exists(clip_path):
        raise HTTPException(status_code=404, detail=f"Audio clip for {line_id} not found")
    return FileResponse(clip_path, media_type="audio/wav", filename=f"{line_id}.wav")

@app.get("/api/voice/play-dub")
def play_combined_dub(project_id: str = Query(...)):
    """Serve full continuous session replacement audio track."""
    dub_path = contained_path(project_path(project_id), "ai_voice_dub.wav")
    if not os.path.exists(dub_path):
        raise HTTPException(status_code=404, detail="ai_voice_dub.wav not found")
    return FileResponse(dub_path, media_type="audio/wav", filename="ai_voice_dub.wav")

@app.get("/api/voice/play-preview")
def play_preview_clip():
    """Serve temporary one-shot preview audio clip."""
    preview_path = os.path.join(PROJECTS_BASE_DIR, "preview_temp.wav")
    if not os.path.exists(preview_path):
        raise HTTPException(status_code=404, detail="preview_temp.wav not found")
    return FileResponse(preview_path, media_type="audio/wav", filename="preview.wav")

@app.get("/api/project/data/{project_id}")
def get_project_data(project_id: str):
    """Retrieve full project manifest, transcripts, director plan, and render status."""
    proj_dir = project_path(project_id)
    if not os.path.exists(proj_dir):
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    def read_json_if_exists(filename):
        p = os.path.join(proj_dir, filename)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    return {
        "project_id": project_id,
        "media": read_json_if_exists("media.json"),
        "transcript": read_json_if_exists("transcript.json"),
        "emotion": read_json_if_exists("emotion.json"),
        "story_map": read_json_if_exists("story_map.json"),
        "english_lines": read_json_if_exists("english_lines.json"),
        "edit_plan": read_json_if_exists("edit_plan.json"),
        "voice_manifest": read_json_if_exists("voice_manifest.json"),
        "render_manifest": read_json_if_exists("render_manifest.json"),
        "api_usage": read_json_if_exists("api_usage.json"),
    }

# --- PHASE 5: MASTER VIDEO RENDERING (NVENC) ---

ACTIVE_RENDER_JOBS: Dict[str, Any] = {}

@app.get("/api/render/probe-encoder")
@serialized
def probe_encoder_endpoint():
    """Detect available hardware encoders."""
    enc = render_engine.probe_best_video_encoder()
    return {"best_encoder": enc}

class RenderStartRequest(BaseModel):
    project_id: str
    preset: str = "YouTube 1440p60"
    encoder: Optional[str] = None
    output_filename: Optional[str] = None

@app.post("/api/render/start")
def start_master_render_endpoint(req: RenderStartRequest):
    """
    Phase 5 Core Render Trigger:
    Launches non-blocking background render worker.
    """
    project_dir = project_path(req.project_id)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project {req.project_id} not found")

    if not WORKER_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another worker is active")
    job_id = f"render_{req.project_id}_{time.time_ns()}"
    ACTIVE_RENDER_JOBS[job_id] = {
        "job_id": job_id,
        "project_id": req.project_id,
        "preset": req.preset,
        "status": "starting",
        "percent": 0.0,
        "current_frame": 0,
        "total_frames": 0,
        "fps": 0.0,
        "elapsed_sec": 0.0,
        "eta_sec": 0.0,
        "encoder": "Detecting...",
        "output_path": None,
        "file_size_mb": 0.0,
        "error": None
    }

    def render_worker():
        def progress_cb(info):
            if job_id in ACTIVE_RENDER_JOBS:
                ACTIVE_RENDER_JOBS[job_id].update(info)

        try:
            manifest = render_engine.render_master_video(
                project_dir=project_dir,
                preset=req.preset,
                encoder_choice=req.encoder,
                output_filename=req.output_filename,
                progress_callback=progress_cb
            )
            ACTIVE_RENDER_JOBS[job_id]["status"] = "completed"
            ACTIVE_RENDER_JOBS[job_id]["percent"] = 100.0
            ACTIVE_RENDER_JOBS[job_id]["manifest"] = manifest
            ACTIVE_RENDER_JOBS[job_id]["output_path"] = manifest.get("output_file")
            ACTIVE_RENDER_JOBS[job_id]["file_size_mb"] = manifest.get("file_size_mb", 0.0)
        except Exception as e:
            ACTIVE_RENDER_JOBS[job_id]["status"] = "error"
            ACTIVE_RENDER_JOBS[job_id]["error"] = str(e)
        finally:
            WORKER_LOCK.release()

    try:
        threading.Thread(target=render_worker, daemon=True).start()
    except Exception:
        WORKER_LOCK.release()
        raise

    return {"success": True, "job_id": job_id}

@app.get("/api/render/status/{job_id}")
def get_render_status(job_id: str):
    """Poll live rendering progress, FPS, percentage, and ETA."""
    if job_id not in ACTIVE_RENDER_JOBS:
        raise HTTPException(status_code=404, detail=f"Render job {job_id} not found")
    return ACTIVE_RENDER_JOBS[job_id]

class OpenFolderRequest(BaseModel):
    file_path: str

@app.post("/api/render/open-folder")
def open_rendered_folder(req: OpenFolderRequest):
    """Open Windows Explorer and select the rendered master video file."""
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="File does not exist")

    try:
        norm_path = os.path.normpath(req.file_path)
        contained_path(PROJECTS_BASE_DIR, norm_path)
        subprocess.Popen(["explorer", "/select,", norm_path])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/render/play-video")
def play_master_video(project_id: str = Query(...)):
    """Stream rendered master video."""
    proj_dir = project_path(project_id)
    manifest_path = os.path.join(proj_dir, "render_manifest.json")
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="Render manifest not found")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    video_path = manifest.get("output_file")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Rendered video file not found")

    contained_path(proj_dir, video_path)
    return FileResponse(video_path, media_type="video/mp4")

class PipelineRequest(BaseModel):
    project_id: str
    api_key: Optional[str] = None
    model_name: str = "gemini-2.5-flash"
    voice_index: int = 0

@app.post("/api/pipeline/start")
def start_pipeline(req: PipelineRequest):
    directory = project_path(req.project_id)
    if not os.path.isfile(os.path.join(directory, "media.json")):
        raise HTTPException(status_code=404, detail="Import the recording first")
    if not WORKER_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another worker is active")
    try:
        write_json(os.path.join(directory, "pipeline.json"), {"status": "queued", "stage": "Starting", "updated_at": time.time()})
        threading.Thread(target=run_pipeline, args=(directory, req.api_key, req.model_name, req.voice_index, True), daemon=True).start()
    except Exception:
        WORKER_LOCK.release()
        raise
    return {"success": True}

@app.get("/api/pipeline/status/{project_id}")
def pipeline_status(project_id: str):
    path = os.path.join(project_path(project_id), "pipeline.json")
    if not os.path.exists(path):
        return {"status": "idle", "stage": "Ready to analyze"}
    with open(path, encoding="utf-8") as stream:
        state = json.load(stream)
    if state["status"] in ("running", "queued") and not WORKER_LOCK.locked() and time.time() - state.get("updated_at", 0) > 5:
        state.update(status="interrupted", stage="Worker stopped. Resume analysis.")
    return state

class RewriteRequest(BaseModel):
    text: str

@app.put("/api/project/{project_id}/line/{line_id}")
def save_rewrite(project_id: str, line_id: str, req: RewriteRequest):
    directory = project_path(project_id)
    identifier(line_id)
    if not req.text.strip() or len(req.text) > 5000:
        raise HTTPException(status_code=400, detail="Enter a nonempty rewrite under 5000 characters")
    with worker_slot():
        path = os.path.join(directory, "english_lines.json")
        with open(path, encoding="utf-8") as stream:
            lines = json.load(stream)
        line = next((line for line in lines if line["line_id"] == line_id), None)
        if line is None:
            raise HTTPException(status_code=404, detail="Dialogue line not found")
        line["english_rewrite"] = req.text.strip()
        write_json(path, lines)
        plan_path = os.path.join(directory, "edit_plan.json")
        with open(plan_path, encoding="utf-8") as stream:
            plan = json.load(stream)
        plan["english_dub_lines"] = lines
        write_json(plan_path, plan)
        clip = contained_path(directory, "voices", f"{line_id}.wav")
        if os.path.isfile(clip):
            os.remove(clip)
        for artifact in ("voice_manifest.json", "render_manifest.json", "voice_cache.json", "ai_voice_dub.wav"):
            target = os.path.join(directory, artifact)
            if os.path.isfile(target):
                os.remove(target)
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    print("[AI GAMING EDITOR] Phase 5 Master Render Daemon on http://127.0.0.1:8765 ...")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info", access_log=False)
