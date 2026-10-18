import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="SethIA Image Engine", version="0.3.0")
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "pollinations").strip().lower()
ENGINE_API_TOKEN = os.getenv("ENGINE_API_TOKEN", "")
POLLINATIONS_BASE_URL = os.getenv(
    "POLLINATIONS_BASE_URL", "https://image.pollinations.ai/prompt"
).rstrip("/")
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
WORKFLOW_PATH = Path(os.getenv("COMFYUI_WORKFLOW_PATH", "workflow.json"))
COMFYUI_TIMEOUT_SECONDS = int(os.getenv("COMFYUI_TIMEOUT_SECONDS", "180"))


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    width: int = Field(default=768, ge=256, le=1024)
    height: int = Field(default=768, ge=256, le=1024)
    steps: int = Field(default=4, ge=1, le=8)
    seed: int | None = None


async def require_token(authorization: str | None = Header(default=None)) -> None:
    if not ENGINE_API_TOKEN:
        raise HTTPException(status_code=503, detail="ENGINE_API_TOKEN is not configured")
    expected = f"Bearer {ENGINE_API_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid API token")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "engine": "sethia-image-engine", "version": "0.3.0"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    if IMAGE_PROVIDER == "pollinations":
        return {"status": "ready", "provider": "pollinations", "api_key_required_by_this_engine": False}
    if IMAGE_PROVIDER == "comfyui":
        if not WORKFLOW_PATH.is_file():
            raise HTTPException(status_code=503, detail="ComfyUI workflow file is missing")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{COMFYUI_URL}/system_stats")
                response.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="ComfyUI is not reachable")
        return {"status": "ready", "provider": "comfyui"}
    raise HTTPException(status_code=503, detail="IMAGE_PROVIDER must be pollinations or comfyui")


async def generate_pollinations(request: GenerateRequest) -> Response:
    url = f"{POLLINATIONS_BASE_URL}/{quote(request.prompt, safe='')}"
    params: dict[str, Any] = {
        "width": request.width,
        "height": request.height,
        "nologo": "true",
        "safe": "true",
    }
    if request.seed is not None:
        params["seed"] = request.seed

    try:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            upstream = await client.get(url, params=params, headers={"Accept": "image/*"})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Image provider timed out; please retry")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach the image provider")

    if upstream.is_error:
        detail = upstream.text[:500] if upstream.text else "No details returned"
        raise HTTPException(status_code=502, detail=f"Image provider error ({upstream.status_code}): {detail}")
    content_type = upstream.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Image provider did not return an image")
    return Response(
        content=upstream.content,
        media_type=content_type.split(";")[0],
        headers={"Cache-Control": "no-store"},
    )


async def generate_comfyui(request: GenerateRequest) -> Response:
    if not WORKFLOW_PATH.is_file():
        raise HTTPException(status_code=503, detail="Configure COMFYUI_WORKFLOW_PATH first")
    try:
        workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
        workflow["6"]["inputs"]["text"] = request.prompt
        workflow["5"]["inputs"]["width"] = request.width
        workflow["5"]["inputs"]["height"] = request.height
        workflow["3"]["inputs"]["steps"] = request.steps
        if request.seed is not None:
            workflow["3"]["inputs"]["seed"] = request.seed
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail=f"Invalid workflow configuration: {exc}")

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            queued = await client.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
            queued.raise_for_status()
            prompt_id = queued.json().get("prompt_id")
            if not prompt_id:
                raise HTTPException(status_code=502, detail="ComfyUI did not return a prompt ID")
            deadline = asyncio.get_running_loop().time() + COMFYUI_TIMEOUT_SECONDS
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(1)
                result = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
                result.raise_for_status()
                history = result.json().get(prompt_id, {})
                for node_output in history.get("outputs", {}).values():
                    for image_data in node_output.get("images", []):
                        params = {
                            "filename": image_data["filename"],
                            "subfolder": image_data.get("subfolder", ""),
                            "type": image_data.get("type", "output"),
                        }
                        downloaded = await client.get(f"{COMFYUI_URL}/view", params=params)
                        downloaded.raise_for_status()
                        return Response(content=downloaded.content, media_type="image/png",
                                        headers={"Cache-Control": "no-store"})
    except HTTPException:
        raise
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not communicate with ComfyUI")
    raise HTTPException(status_code=504, detail="Image generation timed out")


@app.post("/generate", dependencies=[Depends(require_token)])
async def generate(request: GenerateRequest) -> Response:
    if IMAGE_PROVIDER == "pollinations":
        return await generate_pollinations(request)
    if IMAGE_PROVIDER == "comfyui":
        return await generate_comfyui(request)
    raise HTTPException(status_code=503, detail="IMAGE_PROVIDER must be pollinations or comfyui")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "SethIA Image Engine",
        "docs": "/docs",
        "health": "/health",
        "provider": IMAGE_PROVIDER,
        "note": "Set ENGINE_API_TOKEN in the service environment before using /generate.",
    }
