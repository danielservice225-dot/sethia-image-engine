# SethIA Image Engine

Open-source image-generation API for SethIA. It supports a cloud-based **Cloudflare Workers AI** provider (no personal computer or self-hosted GPU required) and an optional separately hosted ComfyUI provider. The API does not bundle model weights.

## Endpoints

- `GET /health`: basic health check.
- `GET /ready`: checks whether the selected provider is configured.
- `POST /generate`: generates and returns a PNG image.
- Bearer-token authentication protects generation requests.

## Recommended cloud setup (Cloudflare Workers AI)

1. Create or sign in to a Cloudflare account and open Workers AI.
2. Find the Cloudflare **Account ID** in the dashboard.
3. Create an API token with the minimum permissions needed to run Workers AI. Never put this token in frontend code or commit it to GitHub.
4. Deploy this repository as a Docker web service on Render.
5. In Render's Environment settings, add:
   - `ENGINE_API_TOKEN`: a long random secret shared only with SethIA's backend.
   - `IMAGE_PROVIDER`: `cloudflare`
   - `CLOUDFLARE_ACCOUNT_ID`: your Cloudflare account ID.
   - `CLOUDFLARE_API_TOKEN`: your Cloudflare API token.
   - `CLOUDFLARE_IMAGE_MODEL`: `@cf/black-forest-labs/flux-1-schnell`
6. Deploy and test `/health`, then `/ready`. Test `POST /generate` from the backend using the bearer token.

Cloudflare's model availability, permissions, limits, and charges/free allowance depend on the account and current Cloudflare terms. Check the dashboard before making the feature public; do not promise unlimited free generation.

## Local configuration

Copy `.env.example` to `.env`, then set the credentials above. Install dependencies and start the API:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs to inspect the API. Example request:

```bash
curl -X POST http://127.0.0.1:8000/generate \\
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"prompt":"A futuristic robot in Abidjan","width":512,"height":512,"steps":4}' \\
  --output generated.png
```

## Optional ComfyUI provider

If you have a separate server running ComfyUI, set `IMAGE_PROVIDER=comfyui`, configure `COMFYUI_URL`, and supply a ComfyUI API-format workflow at `COMFYUI_WORKFLOW_PATH`. The included `workflow.json.example` is only a template: replace the placeholder checkpoint with a model installed on that server. Do not expose ComfyUI port 8188 publicly without appropriate network controls.

## Connecting to SethIA

SethIA's backend must call this API using `Authorization: Bearer YOUR_ENGINE_API_TOKEN` and handle the response as PNG bytes. Keep both Cloudflare credentials and `ENGINE_API_TOKEN` on the server, never in browser JavaScript. Add per-user rate limits, output-size limits, and abuse monitoring before public launch. This repository is not automatically integrated into the SethIA website just by deploying it.

## License

The service code is MIT-licensed. AI model use remains subject to the provider's model license and terms.
