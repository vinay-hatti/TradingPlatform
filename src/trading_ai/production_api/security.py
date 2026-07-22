from __future__ import annotations

import hmac
from fastapi import Header, HTTPException, Request, status

from .config import ProductionApiSettings


def settings_from_request(request: Request) -> ProductionApiSettings:
    return request.app.state.m40_settings


def require_access(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    settings = settings_from_request(request)
    if not settings.require_api_key:
        return "anonymous"
    if not settings.api_key or not x_api_key or not hmac.compare_digest(settings.api_key, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return "api-key"


def require_mutation_access(request: Request, actor: str = Header(default="anonymous", alias="X-Actor"), x_api_key: str | None = Header(default=None)) -> str:
    require_access(request, x_api_key)
    settings = settings_from_request(request)
    if not settings.allow_mutations:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API mutations are disabled")
    return actor
