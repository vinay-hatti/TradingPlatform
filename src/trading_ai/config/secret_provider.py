from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Mapping


class SecretProvider(ABC):
    name = "abstract"

    @abstractmethod
    def get(self, key: str) -> str | None:
        raise NotImplementedError


class EnvironmentSecretProvider(SecretProvider):
    name = "environment"

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def get(self, key: str) -> str | None:
        value = os.getenv(f"{self.prefix}{key}")
        return value if value not in (None, "") else None


class MappingSecretProvider(SecretProvider):
    name = "mapping"

    def __init__(self, values: Mapping[str, str]) -> None:
        self.values = dict(values)

    def get(self, key: str) -> str | None:
        value = self.values.get(key)
        return value if value not in (None, "") else None


class FileSecretProvider(SecretProvider):
    name = "file"

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def get(self, key: str) -> str | None:
        path = self.directory / key
        if not path.is_file():
            return None
        value = path.read_text(encoding="utf-8").strip()
        return value or None


class CompositeSecretProvider(SecretProvider):
    name = "composite"

    def __init__(self, providers: list[SecretProvider] | tuple[SecretProvider, ...]):
        self.providers = tuple(providers)

    def resolve(self, key: str) -> tuple[str | None, str]:
        for provider in self.providers:
            value = provider.get(key)
            if value is not None:
                return value, provider.name
        return None, "unavailable"

    def get(self, key: str) -> str | None:
        return self.resolve(key)[0]


def redact_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}{'*' * max(4, len(value) - 4)}{value[-2:]}"
