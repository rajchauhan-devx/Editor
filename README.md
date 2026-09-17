# AI Gaming Editor

Windows desktop editing prototype with real local workers. **See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) before treating it as production software.**

## Run

Install a compatible Python environment (start with Python 3.11/3.12), Node.js and the worker dependencies:

```powershell
python -m pip install -r python-worker/requirements.txt
npm ci
npm run electron:dev
```

Electron starts the Python worker automatically. Set `AIGE_PYTHON` to an absolute Python executable path if the default `python` command is not the intended environment. Close any older worker on port 8765 before launching this version. The desktop UI needs the authenticated worker introduced in this revision.

1. In Settings, enter a Gemini API key and model ID, then test and save. Desktop storage uses Electron `safeStorage`/Windows OS encryption.
2. Import a recording, inspect it, and confirm separate game-only and microphone-only tracks. A mixed track cannot remove the original microphone reliably.
3. Start/resume analysis on the progress screen. This uploads the proxy and transcript to Gemini and can incur API charges. A hard budget cap is **not implemented**.
4. Review the timeline and English lines. Saved voice edits require regenerating the dub.
5. Export from the original master. Review the result before publishing.

Projects live in `%LOCALAPPDATA%\AIGamingEditor\projects`. The original recording stays at its imported path. Moving or modifying it invalidates source checks; re-import afterward.

## Checks and packaging

```powershell
npm run build
npm run test:worker
npm run dist
```

For an **unsigned local test build** on a machine without executable-signing helper privileges:

```powershell
npm run dist -- '--config.win.signAndEditExecutable=false'
```

The package includes worker source files, not a Python runtime or model weights. It is not yet a standalone clean-machine installer. A signed release requires further packaging work and real-media acceptance.

The backend binds only to `127.0.0.1:8765`. Desktop requests authenticate with a local token. API keys must not be placed in source code, URLs, `.env` committed files or browser local storage. Browser-only `npm run dev` does not provide the desktop credential/token bridge; use `npm run electron:dev` for functional testing.

No mock projects or AI outputs are loaded by the application. Test media and test doubles are isolated to the test suite.
