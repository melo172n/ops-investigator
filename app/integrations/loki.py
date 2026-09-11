import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.investigation import (
    EvidenceCollection,
    EvidenceItem,
    IncidentContext,
)


_BEARER_PATTERN = re.compile(
    r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"
)
_SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|authorization|content)"
    r"(\s*[:=]\s*)(?:[\"']?)[^\s,;\"'}]+(?:[\"']?)"
)
_EMAIL_PATTERN = re.compile(
    r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\b"
)
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)")
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "content",
    "customer_content",
    "password",
    "passwd",
    "phone",
    "pwd",
    "secret",
    "token",
}


class LokiConfigurationError(RuntimeError):
    pass


class LokiCollectionError(RuntimeError):
    pass


class LokiEvidenceCollector:
    source = "loki"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def collect(self, incident: IncidentContext) -> EvidenceCollection:
        query = self._query_for(incident.service)
        start = incident.occurred_at - timedelta(
            minutes=self._settings.loki_window_before_minutes
        )
        end = incident.occurred_at + timedelta(
            minutes=self._settings.loki_window_after_minutes
        )

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.loki_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    self._query_url(),
                    params={
                        "query": query,
                        "start": self._to_nanoseconds(start),
                        "end": self._to_nanoseconds(end),
                        "limit": self._settings.loki_query_limit,
                        "direction": "forward",
                    },
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise LokiCollectionError(
                f"Loki request failed: HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.TransportError, ValueError) as exc:
            raise LokiCollectionError(
                f"Loki request failed: {type(exc).__name__}"
            ) from exc

        items = self._parse_streams(payload, incident.service)
        return EvidenceCollection(
            items=items,
            sources_consulted=["loki"],
        )

    def _query_for(self, service: str) -> str:
        if not self._settings.loki_url.strip():
            raise LokiConfigurationError("Configuração ausente: LOKI_URL")

        query = self._settings.loki_queries_by_service.get(service, "").strip()
        if not query:
            raise LokiConfigurationError(
                f"Nenhuma consulta Loki configurada para o serviço: {service}"
            )
        if not query.startswith("{"):
            raise LokiConfigurationError(
                "A consulta Loki deve começar com um seletor de streams"
            )
        return query

    def _query_url(self) -> str:
        return (
            f"{self._settings.loki_url.rstrip('/')}"
            "/loki/api/v1/query_range"
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        token = self._settings.loki_bearer_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if self._settings.loki_tenant_id:
            headers["X-Scope-OrgID"] = self._settings.loki_tenant_id
        return headers

    def _parse_streams(
        self,
        payload: Any,
        service: str,
    ) -> list[EvidenceItem]:
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise LokiCollectionError("Loki returned an invalid response")

        data = payload.get("data")
        if not isinstance(data, dict) or data.get("resultType") != "streams":
            raise LokiCollectionError("Loki did not return log streams")
        streams = data.get("result")
        if not isinstance(streams, list):
            raise LokiCollectionError("Loki returned malformed log streams")

        parsed: list[tuple[int, EvidenceItem]] = []
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            if not isinstance(labels, dict) or not isinstance(values, list):
                continue
            for value in values:
                item = self._parse_entry(value, labels, service)
                if item is not None:
                    parsed.append(item)

        parsed.sort(key=lambda entry: entry[0])
        return [
            item
            for _, item in parsed[: self._settings.loki_query_limit]
        ]

    def _parse_entry(
        self,
        value: Any,
        labels: dict[str, Any],
        service: str,
    ) -> tuple[int, EvidenceItem] | None:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not isinstance(value[0], str)
            or not isinstance(value[1], str)
        ):
            return None
        try:
            timestamp_ns = int(value[0])
            seconds, nanoseconds = divmod(timestamp_ns, 1_000_000_000)
            observed_at = datetime.fromtimestamp(seconds, UTC).replace(
                microsecond=nanoseconds // 1_000
            )
        except (ValueError, OverflowError, OSError):
            return None

        summary = self._sanitize(value[1])
        if not summary:
            return None
        reference_input = json.dumps(
            {
                "labels": labels,
                "timestamp": value[0],
                "line": value[1],
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(reference_input.encode("utf-8")).hexdigest()[:12]
        return (
            timestamp_ns,
            EvidenceItem(
                reference=f"loki:{value[0]}:{digest}",
                source="loki",
                service=service,
                observed_at=observed_at,
                summary=summary[:2_000],
            ),
        )

    @classmethod
    def _sanitize(cls, line: str) -> str:
        sanitized = (
            _CONTROL_PATTERN.sub("", line)
            .replace("\r", " ")
            .replace("\n", " ")
        )
        try:
            structured = json.loads(sanitized)
        except (TypeError, ValueError):
            pass
        else:
            sanitized = json.dumps(
                cls._redact_json(structured),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return cls._sanitize_text(sanitized)

    @classmethod
    def _redact_json(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if str(key).lower() in _SENSITIVE_KEYS
                    else cls._redact_json(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact_json(item) for item in value]
        if isinstance(value, str):
            return cls._sanitize_text(value)
        return value

    @staticmethod
    def _sanitize_text(value: str) -> str:
        sanitized = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        sanitized = _SECRET_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
            sanitized,
        )
        sanitized = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
        sanitized = _PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
        return " ".join(sanitized.split())

    @staticmethod
    def _to_nanoseconds(value: datetime) -> str:
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        delta = value.astimezone(UTC) - epoch
        seconds = delta.days * 86_400 + delta.seconds
        return str(seconds * 1_000_000_000 + delta.microseconds * 1_000)
