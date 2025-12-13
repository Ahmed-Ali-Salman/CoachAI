"""Mistral API client - HTTP wrapper for multimodal calls."""

import os
import requests
from typing import Any, Dict, Optional


class MistralClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 60):
        self.base_url = (base_url or os.environ.get('MISTRAL_API_URL', 'https://api.mistral.ai')).rstrip('/')
        self.api_key = api_key or os.environ.get('MISTRAL_API_KEY')
        self.timeout = int(timeout)

    def _headers(self) -> Dict[str, str]:
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    def models_list(self) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/models"
        resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def chat_complete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def ocr(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/ocr"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
