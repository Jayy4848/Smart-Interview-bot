from __future__ import annotations

from pathlib import Path

from .config import Settings


class STTClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe(self, audio_path: Path) -> str:
        if self.settings.stt_provider == "openai":
            return await self._transcribe_openai(audio_path)
        return self._transcribe_stub(audio_path)

    def _transcribe_stub(self, audio_path: Path) -> str:
        return "(stub transcript) Configure STT_PROVIDER=openai to enable speech-to-text."

    async def _transcribe_openai(self, audio_path: Path) -> str:
        if not self.settings.openai_api_key:
            return self._transcribe_stub(audio_path)

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        with audio_path.open("rb") as f:
            tr = await client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=f)
        text = getattr(tr, "text", None) or ""
        return str(text).strip() or self._transcribe_stub(audio_path)

