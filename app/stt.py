from __future__ import annotations

import io

from .config import Settings


class STTClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe_bytes(self, audio_bytes: bytes, filename: str) -> str:
        if self.settings.stt_provider == "openai":
            return await self._transcribe_openai_bytes(audio_bytes, filename)
        return self._transcribe_stub()

    def _transcribe_stub(self) -> str:
        return "(stub transcript) Configure STT_PROVIDER=openai to enable speech-to-text."

    async def _transcribe_openai_bytes(self, audio_bytes: bytes, filename: str) -> str:
        if not self.settings.openai_api_key:
            return self._transcribe_stub()

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        audio_file = (filename, io.BytesIO(audio_bytes))
        tr = await client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=audio_file)
        text = getattr(tr, "text", None) or ""
        return str(text).strip() or self._transcribe_stub()

