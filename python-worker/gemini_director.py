from project_safety import write_json
import os
import sys
import json
import re
import time
from project_safety import validate_director, write_json
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

SYSTEM_DIRECTOR_PROMPT = """You are the Gemini Creative Director for the AI Gaming Editor Windows application.
Your role: Transform raw Hindi/Hinglish story-gaming footage into a world-class, engaging YouTube gaming video.

RULES:
1. STORY PRESERVATION FIRST:
   - Identify critical story cutscenes, camp dialogue, reveals, and NPC conversations.
   - Mark these with `protected_story: true` and `action: "protect_keep"`.
   - Hard prohibition: NEVER place distracting memes or sudden cuts inside protected story scenes.
2. PACING & TRAVEL COMPRESSION:
   - Repetitive travel, horse riding, or walking with minimal dialogue should be marked as `action: "compress"` (fast-forward).
3. NATURAL GAMER ENGLISH REWRITES:
   - Translate and rewrite each Hindi/Hinglish reaction into natural worldwide gaming English (the way popular English YouTubers talk).
   - Do NOT produce literal translations. For example:
     * "Bhai ye kaha se aa gaya?" -> "DUDE! Where did this guy come from?!"
     * "Maine bola tha na ye dhoka dega!" -> "I KNEW this guy was going to betray us!"
     * "Arey yaar ghoda upar chadha diya!" -> "You've got to be kidding me... the horse just ran me over!"
   - Ensure the English line length naturally fits the target duration slot.
4. EFFECT SELECTION (ZOOM, SFX, MEMES):
   - Funny deaths: subtle zoom (1.08x - 1.15x), fail_soft or dramatic boom SFX, and optional disappointed_face meme tag.
   - Action hits: subtle snap zoom (1.05x), whoosh SFX.
   - Respect anti-spam: Only place effects on genuine comedic/action beats.

OUTPUT FORMAT:
You MUST respond with valid JSON matching this schema:
{
  "story_summary": "string",
  "story_segments": [
    {
      "start": "HH:MM:SS",
      "end": "HH:MM:SS",
      "start_seconds": float,
      "end_seconds": float,
      "event": "intro" | "cutscene" | "combat" | "funny_death" | "reaction" | "travel" | "dialogue" | "boss",
      "action": "keep" | "compress" | "protect_keep" | "cut",
      "protected_story": bool,
      "notes": "string"
    }
  ],
  "english_lines": [
    {
      "line_id": "string",
      "timestamp": "HH:MM:SS",
      "start_seconds": float,
      "end_seconds": float,
      "original_hindi": "string",
      "english_rewrite": "string",
      "emotion": "Surprised" | "Excited" | "Angry" | "Scared" | "Vindicated" | "Laughing" | "Calm",
      "target_duration_sec": float,
      "zoom": float,
      "sfx": "string" | null,
      "meme": "string" | null
    }
  ]
}
"""

def analyze_session_with_gemini(
    project_dir: str,
    api_key: Optional[str] = None,
    mode: str = "Story",
    model_name: str = "gemini-2.5-flash"
) -> Dict[str, Any]:
    """
    Phase 3 Core Function:
    1. Reads media.json and transcript.json.
    2. Calls Google Gemini 2.5 Flash with full session context.
    3. Receives structured story map & contextual English rewrites.
    4. Compiles persistent story_map.json, english_lines.json, and edit_plan.json.
    5. Updates media.json project state to 'ready_for_voice_generation'.
    """
    media_json_path = os.path.join(project_dir, "media.json")
    transcript_path = os.path.join(project_dir, "transcript.json")

    with open(media_json_path, "r", encoding="utf-8") as f:
        media_data = json.load(f)

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)

    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Configure a Gemini API key before analysis")
    client = genai.Client(api_key=api_key)
    proxy_path = os.path.join(project_dir, "ai_proxy.mp4")
    if not os.path.isfile(proxy_path):
        raise FileNotFoundError("AI proxy not found")
    upload = client.files.upload(file=proxy_path)
    try:
        deadline = time.monotonic() + 600
        while upload.state.name == "PROCESSING":
            if time.monotonic() > deadline:
                raise TimeoutError("Gemini video processing timed out")
            time.sleep(2)
            upload = client.files.get(name=upload.name)
        if upload.state.name != "ACTIVE":
            raise RuntimeError("Gemini could not process the video proxy")
        user_prompt = f"""
GAMEPLAY SESSION CONTEXT:
File: {media_data.get('original_master', {}).get('file_name')}
Duration: {media_data.get('original_master', {}).get('duration_formatted')} ({media_data.get('original_master', {}).get('duration_seconds')} seconds)
Resolution: {media_data.get('original_master', {}).get('resolution')} @ {media_data.get('original_master', {}).get('fps')} FPS
Editing Mode Selected: {mode} Mode

TRANSCRIBED HINDI/HINGLISH SPOKEN LINES:
{json.dumps(transcript_data.get('dialogue_lines', []), indent=2, ensure_ascii=False)}

TASK:
Analyze this session. Protect narrative cutscenes, compress repetitive travel, and rewrite each spoken line into natural worldwide gaming English that matches the target duration.
Cover the entire recording in ordered, contiguous, non-overlapping story segments. Return exactly one English line per transcript ID. Return ONLY valid JSON matching the schema.
"""
        response = client.models.generate_content(
            model=model_name,
            contents=[upload, user_prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_DIRECTOR_PROMPT,
                response_mime_type="application/json",
                temperature=0.4
            )
        )

        response_text = response.text.strip()
        director_output = json.loads(response_text)
        print("[GEMINI DIRECTOR] Successfully received structured story map & rewrites from Gemini API.")
        director_output = validate_director(director_output, transcript_data,
            media_data["original_master"]["duration_seconds"])
        usage = response.usage_metadata
        write_json(os.path.join(project_dir, "api_usage.json"), {
            "model": model_name,
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "cost_usd": None,
            "budget_enforced": False
        })
    finally:
        try:
            client.files.delete(name=upload.name)
        except Exception:
            pass

    # 4. Compile edit_plan.json
    edit_plan_segments = []
    for seg in director_output.get("story_segments", []):
        edit_plan_segments.append({
            "start": seg.get("start"),
            "end": seg.get("end"),
            "start_seconds": seg.get("start_seconds"),
            "end_seconds": seg.get("end_seconds"),
            "event": seg.get("event"),
            "action": seg.get("action"),
            "protected_story": seg.get("protected_story", False),
            "notes": seg.get("notes", "")
        })

    compiled_edit_plan = {
        "project_id": media_data.get("project_id"),
        "project_name": media_data.get("project_name"),
        "director_model": model_name,
        "editing_mode": mode,
        "story_summary": director_output.get("story_summary", ""),
        "total_segments": len(edit_plan_segments),
        "total_rewritten_lines": len(director_output.get("english_lines", [])),
        "story_map": edit_plan_segments,
        "english_dub_lines": director_output.get("english_lines", [])
    }

    # Save outputs
    story_map_file = os.path.join(project_dir, "story_map.json")
    english_lines_file = os.path.join(project_dir, "english_lines.json")
    edit_plan_file = os.path.join(project_dir, "edit_plan.json")

    write_json(story_map_file, director_output.get("story_segments", []))

    write_json(english_lines_file, director_output.get("english_lines", []))

    write_json(edit_plan_file, compiled_edit_plan)

    # Update media.json status to Phase 3 completed
    media_data["phase"] = 3
    media_data["status"] = "ready_for_voice_generation"
    media_data["director_plan"] = {
        "summary": director_output.get("story_summary", ""),
        "edit_plan_path": os.path.abspath(edit_plan_file),
        "story_map_path": os.path.abspath(story_map_file),
        "english_lines_path": os.path.abspath(english_lines_file),
        "lines_count": len(director_output.get("english_lines", []))
    }

    write_json(media_json_path, media_data)

    print(f"[GEMINI DIRECTOR] Phase 3 Complete. Generated edit_plan.json and english_lines.json.")

    return {
        "success": True,
        "story_summary": director_output.get("story_summary", ""),
        "story_map": director_output.get("story_segments", []),
        "english_lines": director_output.get("english_lines", []),
        "edit_plan": compiled_edit_plan,
        "status": "ready_for_voice_generation"
    }
