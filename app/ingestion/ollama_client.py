from __future__ import annotations

import base64
import logging

import httpx

from app.core.config import ExtractPipelineConfig

logger = logging.getLogger(__name__)


def extract_hr_fields(
    image_path: str,
    prompt: str,
    config: ExtractPipelineConfig,
) -> str:
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    url = f"{config.ollama_base_url}/api/chat"
    payload = {
        "model": config.ollama_model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64_image],
            }
        ],
    }
    timeout = httpx.Timeout(config.ollama_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["message"]["content"]