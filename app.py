import asyncio
import os
import secrets
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="SethIA Image Engine", version="0.1.0")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
ENGINE_API_TOKEN = os.getenv("ENGINE_API_TOKEN", "")
WORKFLOW_PATH = Path(os.getenv("COMFYUI_WORKFLOW_PATH", "workflow.json"))
COMFYUI_TIMEOUT_SECONDS = int(os.getenv("COMFYUI_TIMEOUT_SECONDS", "180"))


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    width: int = Field(default=512, ge=256, le=1024)
    height: int = Field(default=512, ge=256, le=1024)
    steps: int = Field(default=20, ge=1, le=40)
    seed: int | None = None


async def require_token(authorization: str | None = Header(default=None)) -> None:
    if not ENGINE_API_TOKEN:
        raise HTTPException(status_code=503, detail="ENGINE_API_TOKEN is not configured")
    expected = f"Bearer {ENGINE_API_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid API token")


@app.get("/health")
async def health() -> dict[str, Any]:
    """Non-sensitive health check; does not expose credentials."""
    return {"status": "ok", "engine": "sethia-image-engine", "version": "0.1.0"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    if not WORKFLOW_PATH.is_file():
        raise HTTPException(status_code=503, detail="ComfyUI workflow file is missing")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{COMFYUI_URL}/system_stats")
            response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="ComfyUI is not reachable")
    return {"status": "ready"}


@app.post("/generate", dependencies=[Depends(require_token)])
async def generate(request: GenerateRequest) -> Response:
    """Generate one PNG using a configured ComfyUI API workflow.

    workflow.json must be exported from ComfyUI in API format and include
    the node IDs configured below. No arbitrary workflow is accepted from callers.
    """
    if not WORKFLOW_PATH.is_file():
        raise HTTPException(status_code=503, detail="Configure COMFYUI_WORKFLOW_PATH first")

    import json

    try:
        workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
        # Default node IDs for the example workflow included in this repository.
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
            history: dict[str, Any] = {}
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(1)
                result = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
                result.raise_for_status()
                history = result.json().get(prompt_id, {})
                outputs = history.get("outputs", {})
                for node_output in outputs.values():
                    for image in node_output.get("images", []):
                        params = {
                            "filename": image["filename"],
                            "subfolder": image.get("subfolder", ""),
                            "type": image.get("type", "output"),
                        }
                        downloaded = await client.get(f"{COMFYUI_URL}/view", params=params)
                        downloaded.raise_for_status()
                        return Response(
                            content=downloaded.content,
                            media_type="image/png",
                            headers={"Cache-Control": "no-store"},
                        )
    except HTTPException:
        raise
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not communicate with ComfyUI")

    raise HTTPException(status_code=504, detail="Image generation timed out")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "SethIA Image Engine",
        "docs": "/docs",
        "health": "/health",
        "note": "Generation requires a configured ComfyUI server and workflow.",
    }
