from __future__ import annotations

from collections.abc import Callable

from sentineldrive_worker.connectors.contracts import Connector, SourceConfig

ConnectorFactory = Callable[[SourceConfig], Connector]


class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ConnectorFactory] = {}

    def register(self, connector_key: str, factory: ConnectorFactory) -> None:
        normalized_key = connector_key.strip().lower()
        if not normalized_key:
            raise ValueError("connector key is required")
        self._factories[normalized_key] = factory

    def create(self, connector_key: str, source: SourceConfig) -> Connector:
        normalized_key = connector_key.strip().lower()
        try:
            factory = self._factories[normalized_key]
        except KeyError as exc:
            raise KeyError(f"connector is not registered: {connector_key}") from exc
        return factory(source)

    def has(self, connector_key: str) -> bool:
        return connector_key.strip().lower() in self._factories

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


registry = ConnectorRegistry()
