from __future__ import annotations

from dataclasses import dataclass

from sentineldrive_worker.connectors.contracts import (
    ConnectorContext,
    ConnectorResult,
    RawIntelligencePayload,
    SourceConfig,
)
from sentineldrive_worker.connectors.nvd_cisa import CisaKevConnector, NvdConnector
from sentineldrive_worker.connectors.nhtsa_recalls import NhtsaRecallsConnector
from sentineldrive_worker.connectors.registry import ConnectorRegistry, registry
from sentineldrive_worker.connectors.rss_vendor import RssConnector, VendorAdvisoryConnector


@dataclass
class SampleConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        item_number = int(context.cursor or "0") + 1
        payload = RawIntelligencePayload.from_source(
            self.source,
            external_id=f"sample-{item_number}",
            title="示例连接器心跳",
            summary="无操作连接器输出，用于验证运行时链路。",
            snippet="连接器运行时就绪",
            raw_content={
                "kind": "sample",
                "cursor": context.cursor,
                "item_number": item_number,
            },
            metadata={"connector": "sample"},
        )
        return ConnectorResult(
            items=(payload,),
            next_cursor=str(item_number),
            metadata={"sample_item_number": item_number},
        )


def register_builtin_connectors(target_registry: ConnectorRegistry = registry) -> ConnectorRegistry:
    target_registry.register("sample", SampleConnector)
    target_registry.register("nvd", NvdConnector)
    target_registry.register("cisa-kev", CisaKevConnector)
    target_registry.register("rss", RssConnector)
    target_registry.register("vendor-advisories", VendorAdvisoryConnector)
    target_registry.register("nhtsa-recalls", NhtsaRecallsConnector)
    return target_registry
