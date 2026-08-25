from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sentineldrive_worker.normalization.models import NormalizationError, Normalizer

NormalizerFactory = Callable[[], Normalizer]


class NormalizerRegistry:
    def __init__(self) -> None:
        self._by_source_name: dict[str, NormalizerFactory] = {}
        self._by_source_type: dict[str, NormalizerFactory] = {}
        self._by_entry_origin: dict[str, NormalizerFactory] = {}

    def register_source_name(self, source_name: str, factory: NormalizerFactory) -> None:
        self._by_source_name[normalize_key(source_name)] = factory

    def register_source_type(self, source_type: str, factory: NormalizerFactory) -> None:
        self._by_source_type[normalize_key(source_type)] = factory

    def register_entry_origin(self, entry_origin: str, factory: NormalizerFactory) -> None:
        self._by_entry_origin[normalize_key(entry_origin)] = factory

    def resolve(self, raw_record: Mapping[str, Any]) -> Normalizer:
        source_name = normalize_key(raw_record.get("source_name"))
        if source_name in self._by_source_name:
            return self._by_source_name[source_name]()
        metadata = raw_record.get("metadata")
        entry_origin = normalize_key((metadata or {}).get("entry_origin")) if isinstance(metadata, Mapping) else ""
        if entry_origin in self._by_entry_origin:
            return self._by_entry_origin[entry_origin]()
        source_type = normalize_key(raw_record.get("source_type"))
        if source_type in self._by_source_type:
            return self._by_source_type[source_type]()
        raise NormalizationError(f"no normalizer registered for source {raw_record.get('source_name') or raw_record.get('source_type')}")


def normalize_key(value: object) -> str:
    return str(value or "").strip().lower()


registry = NormalizerRegistry()
