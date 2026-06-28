from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError


DEFAULT_API_BASE = "https://api.x.com/2"


@dataclass(frozen=True)
class XBearerCredentials:
    bearer_token: str

    @classmethod
    def from_env(cls) -> "XBearerCredentials | None":
        token = os.environ.get("X_BEARER_TOKEN", "")
        return cls(token) if token else None


@dataclass(frozen=True)
class XCredentials:
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str

    @classmethod
    def from_env(cls) -> "XCredentials":
        env_map = {
            "api_key": "X_API_KEY",
            "api_secret": "X_API_SECRET",
            "access_token": "X_ACCESS_TOKEN",
            "access_token_secret": "X_ACCESS_TOKEN_SECRET",
        }
        values = {field: os.environ.get(env_name, "") for field, env_name in env_map.items()}
        missing = [env_map[field] for field, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing X credential environment variable(s): {', '.join(missing)}")
        return cls(**values)


class XPublisher:
    def __init__(self, credentials: XCredentials, api_base: str = DEFAULT_API_BASE) -> None:
        self.credentials = credentials
        self.api_base = api_base.rstrip("/")

    def post_draft(self, draft: dict) -> list[str]:
        return _post_draft_with_client(draft, self)

    def post(self, text: str, media_ids: list[str] | None = None, reply_to_id: str | None = None) -> str:
        url = f"{self.api_base}/tweets"
        payload = _post_payload(text, media_ids, reply_to_id)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": _oauth_header("POST", url, self.credentials),
            "Content-Type": "application/json",
            "User-Agent": "x-daily-poster/0.1",
        }
        req = request.Request(url, data=body, headers=headers, method="POST")

        payload = _open_json(req)
        post_id = _extract_post_id(payload)
        if not post_id:
            raise RuntimeError(f"X API response did not include a post ID: {payload}")
        return post_id

    def upload_media(self, image_path: str) -> str:
        return _upload_media_oauth1(self, image_path)


class XBearerPublisher:
    def __init__(self, credentials: XBearerCredentials, api_base: str = DEFAULT_API_BASE) -> None:
        self.credentials = credentials
        self.api_base = api_base.rstrip("/")

    def post_draft(self, draft: dict) -> list[str]:
        return _post_draft_with_client(draft, self)

    def post(self, text: str, media_ids: list[str] | None = None, reply_to_id: str | None = None) -> str:
        url = f"{self.api_base}/tweets"
        payload = _post_payload(text, media_ids, reply_to_id)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.credentials.bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "x-daily-poster/0.1",
        }
        req = request.Request(url, data=body, headers=headers, method="POST")
        payload = _open_json(req)
        post_id = _extract_post_id(payload)
        if not post_id:
            raise RuntimeError(f"X API response did not include a post ID: {payload}")
        return post_id

    def upload_media(self, image_path: str) -> str:
        return _upload_media_bearer(self, image_path)


class DryRunPublisher:
    def post_draft(self, draft: dict) -> list[str]:
        parts = draft.get("parts") or [draft.get("text", "")]
        media_ids = [self.upload_media(draft["image_path"])] if draft.get("image_path") else []
        posted_ids: list[str] = []
        reply_to_id: str | None = None
        for index, part in enumerate(parts):
            attached_media = media_ids if index == 0 else None
            posted_id = self.post(part, media_ids=attached_media, reply_to_id=reply_to_id)
            posted_ids.append(posted_id)
            reply_to_id = posted_id
        return posted_ids

    def post(self, text: str, media_ids: list[str] | None = None, reply_to_id: str | None = None) -> str:
        digest_input = "|".join([text, ",".join(media_ids or []), reply_to_id or ""])
        digest = hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:12]
        return f"dryrun-{digest}"

    def upload_media(self, image_path: str) -> str:
        digest = hashlib.sha1(image_path.encode("utf-8")).hexdigest()[:12]
        return f"dryrun-media-{digest}"


def publisher_from_env() -> XBearerPublisher | XPublisher:
    bearer_credentials = XBearerCredentials.from_env()
    if bearer_credentials:
        return XBearerPublisher(bearer_credentials)
    return XPublisher(XCredentials.from_env())


def _open_json(req: request.Request) -> dict[str, Any]:
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X API request failed with HTTP {exc.code}: {error_body}") from exc


def _extract_post_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    return None


def _extract_media_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict):
        media_id = data.get("id") or data.get("media_id")
        if media_id:
            return str(media_id)
    media_id = payload.get("media_id_string") or payload.get("media_id")
    return str(media_id) if media_id else None


def _post_draft_with_client(draft: dict, client: Any) -> list[str]:
    parts = draft.get("parts") or [draft.get("text", "")]
    image_path = draft.get("image_path")
    media_ids: list[str] = []
    if image_path:
        media_ids.append(client.upload_media(image_path))

    posted_ids: list[str] = []
    reply_to_id: str | None = None
    for index, part in enumerate(parts):
        attached_media = media_ids if index == 0 else None
        posted_id = client.post(part, media_ids=attached_media, reply_to_id=reply_to_id)
        posted_ids.append(posted_id)
        reply_to_id = posted_id
    return posted_ids


def _post_payload(text: str, media_ids: list[str] | None, reply_to_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"text": text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
    return payload


def _upload_media_bearer(client: XBearerPublisher, image_path: str) -> str:
    url = f"{client.api_base}/media/upload"
    body, content_type = _multipart_body(image_path)
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {client.credentials.bearer_token}",
            "Content-Type": content_type,
            "User-Agent": "x-daily-poster/0.1",
        },
        method="POST",
    )
    payload = _open_json(req)
    media_id = _extract_media_id(payload)
    if not media_id:
        raise RuntimeError(f"X media upload response did not include a media ID: {payload}")
    return media_id


def _upload_media_oauth1(client: XPublisher, image_path: str) -> str:
    url = f"{client.api_base}/media/upload"
    body, content_type = _multipart_body(image_path)
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": _oauth_header("POST", url, client.credentials),
            "Content-Type": content_type,
            "User-Agent": "x-daily-poster/0.1",
        },
        method="POST",
    )
    payload = _open_json(req)
    media_id = _extract_media_id(payload)
    if not media_id:
        raise RuntimeError(f"X media upload response did not include a media ID: {payload}")
    return media_id


def _multipart_body(image_path: str) -> tuple[bytes, str]:
    path = Path(image_path)
    if not path.is_file():
        raise RuntimeError(f"Image file does not exist: {image_path}")

    boundary = f"xposter-{uuid.uuid4().hex}"
    content_type = _guess_content_type(path)
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="media"; filename="{path.name}"\r\n'.encode(
                "utf-8"
            ),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _oauth_header(method: str, url: str, credentials: XCredentials) -> str:
    oauth_params = {
        "oauth_consumer_key": credentials.api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": credentials.access_token,
        "oauth_version": "1.0",
    }
    signature = _sign(method, url, oauth_params, credentials)
    oauth_params["oauth_signature"] = signature
    return "OAuth " + ", ".join(
        f'{_quote(key)}="{_quote(value)}"' for key, value in sorted(oauth_params.items())
    )


def _sign(method: str, url: str, params: dict[str, str], credentials: XCredentials) -> str:
    parsed = parse.urlsplit(url)
    base_url = parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    query_params = dict(parse.parse_qsl(parsed.query, keep_blank_values=True))
    signing_params = {**query_params, **params}
    param_string = "&".join(
        f"{_quote(key)}={_quote(value)}" for key, value in sorted(signing_params.items())
    )
    base_string = "&".join([method.upper(), _quote(base_url), _quote(param_string)])
    signing_key = f"{_quote(credentials.api_secret)}&{_quote(credentials.access_token_secret)}"
    digest = hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _quote(value: object) -> str:
    return parse.quote(str(value), safe="~")
