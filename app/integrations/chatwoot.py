from dataclasses import dataclass

import httpx

from app.core.config import Settings


class ChatwootError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatwootMessage:
    message_id: int | None
    skipped: bool = False


class ChatwootClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_operations_message(self, content: str) -> ChatwootMessage:
        if not self._settings.chatwoot_enabled:
            return ChatwootMessage(message_id=None, skipped=True)

        self._validate_configuration()
        url = (
            f"{self._settings.chatwoot_url.rstrip('/')}/api/v1/accounts/"
            f"{self._settings.chatwoot_account_id}/conversations/"
            f"{self._settings.chatwoot_operations_conversation_id}/messages"
        )
        headers = {
            "api_access_token": (
                self._settings.chatwoot_api_token.get_secret_value()
            )
        }
        payload = {
            "content": content,
            "message_type": "outgoing",
            "private": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChatwootError(f"Falha ao enviar mensagem ao Chatwoot: {exc}") from exc

        data = response.json()
        return ChatwootMessage(message_id=data.get("id"))

    def _validate_configuration(self) -> None:
        missing = []
        if not self._settings.chatwoot_url:
            missing.append("CHATWOOT_URL")
        if not self._settings.chatwoot_api_token.get_secret_value():
            missing.append("CHATWOOT_API_TOKEN")
        if self._settings.chatwoot_account_id <= 0:
            missing.append("CHATWOOT_ACCOUNT_ID")
        if self._settings.chatwoot_operations_conversation_id <= 0:
            missing.append("CHATWOOT_OPERATIONS_CONVERSATION_ID")
        if missing:
            fields = ", ".join(missing)
            raise ChatwootError(f"Configuração ausente: {fields}")

