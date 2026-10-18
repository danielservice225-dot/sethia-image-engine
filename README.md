# SethIA Image Engine

Open-source image-generation API for SethIA. The default provider uses the hosted Pollinations image endpoint, so this repository does not require a local GPU or Cloudflare credentials. A separately hosted ComfyUI server is also supported. The repository itself does not contain AI model weights.

## Endpoints

- `GET /health`: basic health check.
- `GET /ready`: checks the selected provider configuration.
- `POST /generate`: generates an image and returns image bytes.
- Bearer-token authentication protects generation requests.

## Deploy on Render

1. Create a **Web Service** from this GitHub repository, branch `main`, runtime **Docker**.
2. In Render Environment, set:
   - `ENGINE_API_TOKEN`: a long random secret shared only with SethIA's backend. Keep it secret.
   - `IMAGE_PROVIDER`: `pollinations`
   - `POLLINATIONS_BASE_URL`: `https://image.pollinations.ai/prompt`
3. Deploy, then check `/health` and `/ready`.
4. Test `POST /generate` from a backend or API client with header `Authorization: Bearer YOUR_SECRET_TOKEN` and JSON such as:
   `{"prompt":"A futuristic African city at sunset","width":768,"height":768,"steps":4}`.
   The response should be image bytes.

**Important:** Pollinations is an external hosted service. Access, availability, rate limits, model behavior, and any API-key requirements may change. This setup is not a guarantee of unlimited free generation. If the provider returns an error or non-image response, check its current API documentation and service status.

## Local setup

Copy `.env.example` to `.env`, set a private `ENGINE_API_TOKEN`, then run:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` to inspect the API.

## Optional ComfyUI

If you operate a separate machine/server running ComfyUI, set `IMAGE_PROVIDER=comfyui`, configure `COMFYUI_URL`, and provide a compatible workflow at `COMFYUI_WORKFLOW_PATH`. The example workflow is only a template and requires a model installed on that server. Do not expose ComfyUI port 8188 publicly without network controls.

## Connecting to SethIA

SethIA's backend must call this service using `Authorization: Bearer YOUR_ENGINE_API_TOKEN` and handle the response as image bytes. Keep the token on the server, never in browser JavaScript. Add per-user rate limits and abuse monitoring before making image generation public.

**Deploying this repository does not automatically connect it to the separate SethIA website.** The SethIA backend still needs to be configured to call this service.

## License

The service code is MIT-licensed. The hosted image provider's model usage remains subject to its own terms.
