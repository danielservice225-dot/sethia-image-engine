# SethIA Image Engine

Open-source image generation API for SethIA. This service is a lightweight, authenticated FastAPI bridge to a separately running [ComfyUI](https://github.com/comfyanonymous/ComfyUI) server. It does **not** bundle AI model weights.

## What it provides

- `GET /health`: basic service health check.
- `GET /ready`: checks the workflow file and ComfyUI connectivity.
- `POST /generate`: submits a prompt to ComfyUI and returns a generated PNG.
- Bearer-token protection for the generation endpoint.
- Request limits for prompt length, image dimensions, and steps.

## Requirements

- Python 3.11+ (Docker image uses Python 3.12).
- A running ComfyUI server with a model/checkpoint installed.
- A ComfyUI workflow exported in **API format**. The example workflow expects the node IDs shown in `workflow.json.example`.

## Run locally

1. Install and start ComfyUI using its official instructions: https://github.com/comfyanonymous/ComfyUI
2. Copy `.env.example` to `.env` and set a strong random `ENGINE_API_TOKEN`.
3. Copy `workflow.json.example` to `workflow.json` and replace `REPLACE_WITH_YOUR_MODEL.safetensors` with the exact checkpoint filename installed in ComfyUI.
4. Install dependencies and start the API:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

The app reads the `.env` file automatically. Never commit `.env` or `workflow.json`.

Open http://127.0.0.1:8000/docs to inspect the API.

## Test generation

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"A friendly futuristic robot in Abidjan","width":512,"height":512,"steps":20}' \
  --output generated.png
``

The response is a PNG image. The service returns errors if ComfyUI or the workflow is not configured.

## Deploying and connecting to SethIA

The API and ComfyUI must both be reachable from each other. For an at-home computer, **do not expose ComfyUI port 8188 directly to the public Internet**. Use a private network or an authenticated tunnel (for example, Cloudflare Tunnel with Access), and configure `COMFYUI_URL` to the URL reachable from this API service.

In Render, set `ENGINE_API_TOKEN` as a secret environment variable. Keep it server-side; never place it in frontend JavaScript or commit it to GitHub. SethIA's backend should call this API using the bearer token. Do not allow anonymous image generation, and add user-level rate limits before making it available to the public.

A free Render web service may sleep or have limited resources; it does not supply a GPU for ComfyUI image generation. Running this API on Render does not mean the model itself runs on Render.

## Important limitations

- The example workflow uses common ComfyUI node IDs; if you change the workflow, update the node IDs in `app.py` too.
- The checkpoint filename must match a model installed in ComfyUI.
- The first version returns PNG bytes directly; SethIA's backend must store or forward the image appropriately.
- This is a starter project, not yet integrated into the existing SethIA repository or production website.

## License

This project code is released under the MIT License. AI model files have their own separate licenses; verify the license of each model you download.
