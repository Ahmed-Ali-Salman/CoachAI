"""Model loading and inference handling for CoachAI.

Supports remote Mistral API backend (default). This module is framework-agnostic.
"""

import os
import io
import base64
from typing import Any, Dict, Optional, List

from coachai.clients.mistral_client import MistralClient


class ModelHandler:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.processor = None
        self.device = None
        self._mistral_client: Optional[MistralClient] = None

    def load_model(self) -> bool:
        if getattr(self.config, 'USE_REMOTE_MODEL', False):
            success = self._init_remote_client()
            if success:
                self.device = 'remote:mistral'
            return success
        # Local mode is not implemented in this repo.
        return False

    def _init_remote_client(self) -> bool:
        api_key = getattr(self.config, 'MISTRAL_API_KEY', None) or os.environ.get('MISTRAL_API_KEY')
        if not api_key:
            return False

        try:
            self._mistral_client = MistralClient(
                base_url=getattr(self.config, 'MISTRAL_API_URL', None),
                api_key=api_key,
                timeout=getattr(self.config, 'MISTRAL_TIMEOUT_SECONDS', 30)
            )
            self._mistral_client.models_list()
            return True
        except Exception:
            return False

    def generate(self, messages: List[Dict[str, Any]], max_new_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        if getattr(self.config, 'USE_REMOTE_MODEL', False):
            if not self._mistral_client and not self._init_remote_client():
                return 'Error: Remote client not initialized'
            return self._generate_remote(messages, max_new_tokens=max_new_tokens, temperature=temperature)

        return 'Error: Local model not available'

    def _encode_image_to_base64(self, pil_image, fmt: str = 'PNG') -> Optional[str]:
        try:
            buffer = io.BytesIO()
            pil_image.save(buffer, format=fmt)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/{fmt.lower()};base64,{b64}"
        except Exception:
            return None

    def _convert_messages_for_remote(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content')

            if isinstance(content, list):
                new_content = []
                for c in content:
                    if isinstance(c, dict) and 'image' in c:
                        img = c.get('image')
                        try:
                            from PIL import Image as PILImage
                            if isinstance(img, PILImage.Image):
                                data_url = self._encode_image_to_base64(img)
                                if data_url:
                                    if getattr(self.config, 'MISTRAL_USE_IMAGE_URLS', True):
                                        new_content.append({'type': 'image_url', 'image_url': data_url})
                                    else:
                                        new_content.append({'type': 'image_base64', 'image_base64': data_url})
                                else:
                                    new_content.append({'type': 'text', 'text': '[Image could not be encoded]'})
                            else:
                                url = c.get('url') or c.get('image_url')
                                if url:
                                    new_content.append({'type': 'image_url', 'image_url': url})
                                else:
                                    new_content.append({'type': 'text', 'text': '[Image payload]'})
                        except Exception:
                            new_content.append({'type': 'text', 'text': '[Image payload]'})
                    elif isinstance(c, dict) and 'text' in c:
                        new_content.append({'type': 'text', 'text': c.get('text')})
                    elif isinstance(c, str):
                        new_content.append({'type': 'text', 'text': c})
                    else:
                        new_content.append({'type': 'text', 'text': str(c)})

                converted.append({'role': role, 'content': new_content})
            else:
                converted.append({'role': role, 'content': [{'type': 'text', 'text': str(content)}]})

        return converted

    def _generate_remote(self, messages: List[Dict[str, Any]], max_new_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        try:
            max_tokens = max_new_tokens or getattr(self.config, 'MAX_TOKENS', 1024)
            temperature = temperature if temperature is not None else getattr(self.config, 'TEMPERATURE', 0.7)

            payload_messages = self._convert_messages_for_remote(messages)

            payload = {
                'model': getattr(self.config, 'MISTRAL_MODEL', getattr(self.config, 'MODEL_NAME', 'mistral-medium-2508')),
                'messages': payload_messages,
                'temperature': float(temperature),
                'max_tokens': int(max_tokens)
            }

            data = self._mistral_client.chat_complete(payload)

            if 'choices' in data and len(data['choices']) > 0:
                message = data['choices'][0].get('message')
                if isinstance(message, dict):
                    content = message.get('content')
                    if isinstance(content, list):
                        texts = [c.get('text') for c in content if isinstance(c, dict) and 'text' in c]
                        return "\n".join(t for t in texts if t)
                    if isinstance(content, str):
                        return content
                    return str(content)
                return str(message)

            return str(data)
        except Exception as e:
            return f"Remote generation error: {e}"
