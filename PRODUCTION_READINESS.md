# Workflow audit — 17 September 2026

**Release decision: not ready for production.** The original project mixed working local media functions with a substantial UI prototype. This revision removes fabricated runtime results and makes the basic workflow testable. It does not establish that all six product phases have shipped.

The implementation uses **Electron + React + Python**, not the Tauri stack in the supplied plan. A framework migration was not required for these fixes.

## Phase acceptance

| Phase | Status after this revision | Evidence and remaining work |
| --- | --- | --- |
| V0 — Dubbing POC | Partial; needs real-recording acceptance | Real inspection, confirmed separate tracks, VAD/Whisper, Gemini rewrite, system TTS, separate game/dub mixing and subtitles are connected. Silence is no longer replaced with invented dialogue. TTS rejects lines that exceed their slots. Natural Hindi/Hinglish rewrite quality, English voice quality and a 10–20-minute OBS recording have not been validated. System voices do not preserve emotions. |
| V1 — Auto Edit | Basic implementation; not production validated | Gemini now receives the video proxy. Director output is validated. Cut/compress timing is shared across source video, game audio, dub and subtitles. A synthetic FFmpeg integration test verifies output duration and subtitle remapping. Long-session memory use, scene coverage and pacing require acceptance tests. |
| V2 — YouTube Style | Not implemented | Asset storage/tagging, effect rendering, replay, death montage and actual acoustic emotion analysis are missing. Unsupported effect output is disabled. Demo asset/model/effect controls were removed. |
| V3 — Story Mode | Partial | Protected regions cannot be cut/compressed; reaction windows are kept; malformed and incomplete story maps are rejected. Continuity memory, important-choice tracking and NPC speech detection/voice placement are missing. Model-generated story understanding is not a guarantee against narrative mistakes. |
| V4 — Enhancement | Resolution scaling only | Original-master export supports 1080p, 1440p and 4K using Lanczos. No scene-aware grading, highlight recovery, restoration or neural upscaling is implemented. UI now says so. |
| V5 — AI Review | Not implemented | No representative preview generation, Gemini critique/correction loop or personalization. The proxy player is explicitly labeled as an original preview. |

## Defects corrected

- Removed seeded projects, scenes, dialogues, assets, model installation states, synthetic progress logs and fake hardware/connection/cost displays. Kept legitimate presets, configuration defaults and isolated test fixtures.
- Removed the offline “Gemini” fallback that invented story maps and rewrites. Missing credentials/API failures stop processing.
- Removed short-silence demo transcripts; ASR failures now propagate and unload the model.
- Import waits for extraction/proxy completion, preserves the backend project ID, obeys React hook ordering, clears stale inspection results and requires distinct confirmed audio tracks.
- Added real desktop file selection and start/resume analysis. Successful stages have cache receipts; interrupted jobs retain durable status. JSON artifacts are replaced atomically.
- Added output schema/time/identifier validation, transcript-line identity checks, and story-region protection.
- Added deterministic cut/compress rendering and corresponding subtitle remapping. Invalid edits overlapping dialogue fail rather than cutting a voice line silently.
- FFmpeg errors no longer count as success. Export cannot silently drop subtitles or fall back to mixed source microphone audio. The rendered MP4 is published only after successful encoding.
- Voice edits persist, synchronize the plan, and invalidate stale dub/export artifacts. Excessively long voice clips require a shorter rewrite.
- Added a shared worker lock for direct media/ASR/TTS/render operations and pipeline execution.
- Added local API authentication, restricted CORS/Host checks, traversal-safe project/clip paths and source-overwrite checks. Disabled query-string access logging because media URLs carry the local token.
- Added Electron OS-encrypted key storage, sandboxed preload, trusted IPC checks and navigation restrictions. Removed the hardcoded demo key and false encryption claims.
- Corrected CSP to allow the authenticated local worker while removing broad external script/eval permissions and remote font requests.
- Added missing Python dependencies, packaged Python worker sources, automatic desktop worker startup and corrected setup/launch scripts.

## Release blockers

1. **Billing guard:** token usage is recorded, but dollar-cost calculation, reservation/reconciliation and an enforced project budget are missing. UI explicitly warns about this. Do not market a $2 cap.
2. **Real-media acceptance:** run the plan's 10–20-minute Hindi/Hinglish OBS milestone using separate mic/game tracks and a real Gemini key. Verify meaning, voice quality, timing, NPC dialogue, subtitles, all edit boundaries and original-master quality. No external API calls were made during this audit.
3. **Long-session reliability:** stress-test two-hour sessions, hundreds of speech clips, disk exhaustion, corrupted caches, source replacement, app shutdown, duplicate starts and multi-process worker ownership. The current TTS assembly uses many FFmpeg input arguments and full-length WAVs; chunked assembly is needed for predictable memory and Windows argument limits.
4. **State management:** atomic JSON/cache receipts are an improvement, but the requested SQLite `project_state.db`, event bus, job cancellation and durable render resumption are not implemented. Interrupted stages restart; cached successful stages can be reused.
5. **Media understanding:** local `scene_map.json`/OCR, reusable expiring Gemini upload references and rich project context are missing. The uploaded proxy is deleted after each uncached analysis. Video sampling may miss short events.
6. **Safety/quality:** current ducking reduces game audio beneath the dub; it does not detect or protect NPC speech. Audio emotion is a text heuristic. Protected-scene accuracy depends on Gemini and must be reviewed.
7. **Packaging/dependencies:** Python and dependencies must still be installed separately. Pin and validate a supported Python/native-library matrix, bundle the runtime for a true standalone installer, provide signing and test on a clean Windows machine. Electron dependencies also need a supported-version/security review before release.
8. **Incomplete product phases:** implement V2, the remaining V3 guarantees, V4 enhancement and V5 review before claiming the full workflow.

## Validation

- `npm run build`: TypeScript and production Vite build pass.
- `python -m unittest discover -s python-worker -p test_*.py -v`: 15 tests pass, including actual synthetic-media FFmpeg encoding, shortened output duration, subtitle timing and unchanged source metadata.
- Tests cover API authentication, hostile origin rejection, path traversal, silence, ASR failure propagation, missing Gemini credentials, protected story regions and shared worker exclusion.
- `python -m compileall -q python-worker` and `node --check electron/main.cjs`: pass.
- No real API key, paid Gemini request, model download or user gameplay export was used in automated tests.
- Desktop packaging produced the unpacked app and included the Python worker. The portable EXE build did not complete: Windows denied signing-helper symlinks; an unsigned retry then failed because the NSIS `Nsis7z` plugin could not be installed in the builder cache. Existing older ZIPs are not this revision.
- Interactive desktop smoke testing could not run: the computer-use app-launch approval timed out. UI behavior is build-checked, not visually verified.

Tests do not prove natural-language quality, GPU-specific behavior, production-scale throughput or end-to-end Gemini/TTS acceptance. Do not infer phase completion from compilation or the synthetic export.

Gemini video upload/processing flow was checked against Google's [official video-understanding documentation](https://ai.google.dev/gemini-api/docs/video-understanding).

## Existing prototype projects

Old on-disk projects may contain fabricated transcript/plan files from the previous demo fallback. They are not silently deleted or trusted as newly validated results. Re-import the original recording into a new project for acceptance testing. Keep originals and previous outputs until reviewed.

