import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatwootAttempt:
    status: str
    external_message_id: int | None = None
    detail: str | None = None


class ChatwootError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        attempts: tuple[ChatwootAttempt, ...] = (),
    ) -> None:
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True)
class ChatwootMessage:
    message_id: int | None
    skipped: bool = False
    attempts: tuple[ChatwootAttempt, ...] = ()


class ChatwootClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._sleep = sleep

    async def send_operations_message(self, content: str) -> ChatwootMessage:
        if not self._settings.chatwoot_enabled:
            return ChatwootMessage(
                message_id=None,
                skipped=True,
                attempts=(
                    ChatwootAttempt(
                        status="skipped",
                        detail="CHATWOOT_ENABLED=false",
                    ),
                ),
            )

        self._validate_configuration()
        url = (
            f"{self._settings.chatwoot_url.rstrip('/')}/api/v1/accounts/"
            f"{self._settings.chatwoot_account_id}/conversations/"
            f"{self._settings.chatwoot_operations_conversation_id}/messages"
        )
        headers = {
            "api_access_token": self._settings.chatwoot_api_token.get_secret_value()
        }
        payload = {
            "content": content,
            "message_type": "outgoing",
            "private": False,
        }
        attempts: list[ChatwootAttempt] = []
        max_attempts = self._settings.chatwoot_max_attempts

        async with httpx.AsyncClient(
            timeout=10.0,
            transport=self._transport,
        ) as client:
            for attempt_number in range(1, max_attempts + 1):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    detail = f"HTTP {status_code}"
                    retryable = status_code == 429 or status_code >= 500
                    ambiguous = status_code >= 500
                except httpx.TransportError as exc:
                    detail = type(exc).__name__
                    retryable = True
                    ambiguous = not isinstance(
                        exc,
                        (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout),
                    )
                else:
                    message_id = self._message_id(response)
                    attempts.append(
                        ChatwootAttempt(
                            status="sent",
                            external_message_id=message_id,
                        )
                    )
                    logger.info(
                        "chatwoot_notification_attempt status=sent attempt=%s "
                        "max_attempts=%s external_message_id=%s",
                        attempt_number,
                        max_attempts,
                        message_id,
                    )
                    return ChatwootMessage(
                        message_id=message_id,
                        attempts=tuple(attempts),
                    )

                if ambiguous:
                    await self._sleep(self._retry_delay(attempt_number))
                    try:
                        confirmed_id = await self._find_existing_message(
                            client,
                            url=url,
                            headers=headers,
                            content=content,
                        )
                    except ChatwootError as exc:
                        attempts.append(
                            ChatwootAttempt(status="failed", detail=detail)
                        )
                        raise ChatwootError(
                            str(exc),
                            attempts=tuple(attempts),
                        ) from exc
                    if confirmed_id is not None:
                        confirmation_detail = (
                            f"delivery confirmed after ambiguous failure: {detail}"
                        )
                        attempts.append(
                            ChatwootAttempt(
                                status="sent",
                                external_message_id=confirmed_id,
                                detail=confirmation_detail,
                            )
                        )
                        logger.info(
                            "chatwoot_notification_attempt status=sent attempt=%s "
                            "max_attempts=%s confirmation=recovered "
                            "external_message_id=%s",
                            attempt_number,
                            max_attempts,
                            confirmed_id,
                        )
                        return ChatwootMessage(
                            message_id=confirmed_id,
                            attempts=tuple(attempts),
                        )

                attempts.append(ChatwootAttempt(status="failed", detail=detail))
                will_retry = retryable and attempt_number < max_attempts
                logger.warning(
                    "chatwoot_notification_attempt status=failed attempt=%s "
                    "max_attempts=%s retry=%s error=%s",
                    attempt_number,
                    max_attempts,
                    str(will_retry).lower(),
                    detail,
                )

                if not will_retry:
                    raise ChatwootError(
                        f"Falha ao enviar mensagem ao Chatwoot: {detail}",
                        attempts=tuple(attempts),
                    )

                if not ambiguous:
                    await self._sleep(self._retry_delay(attempt_number))

        raise ChatwootError(
            "Falha ao enviar mensagem ao Chatwoot",
            attempts=tuple(attempts),
        )

    async def _find_existing_message(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        content: str,
    ) -> int | None:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            detail = type(exc).__name__
            logger.warning(
                "chatwoot_delivery_confirmation status=failed error=%s",
                detail,
            )
            raise ChatwootError(
                "Falha ambígua no Chatwoot; confirmação de entrega indisponível"
            ) from exc

        messages = data.get("payload", []) if isinstance(data, dict) else []
        for message in messages:
            if not isinstance(message, dict) or message.get("content") != content:
                continue
            message_id = message.get("id")
            return message_id if isinstance(message_id, int) else None
        return None

    def _retry_delay(self, attempt_number: int) -> float:
        return self._settings.chatwoot_retry_base_delay_seconds * (
            2 ** (attempt_number - 1)
        )

    @staticmethod
    def _message_id(response: httpx.Response) -> int | None:
        try:
            data = response.json()
        except ValueError:
            return None
        message_id = data.get("id") if isinstance(data, dict) else None
        return message_id if isinstance(message_id, int) else None

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
