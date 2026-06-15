import { PageSection, WorkbenchShell } from "../../components/WorkbenchShell";
import { IntelligenceDetailPanel } from "./DetailPanel";

export default async function IntelligenceDetailPage({ params }) {
  const { id: itemId } = await params;

  return (
    <WorkbenchShell active="/" eyebrow="情报详情" title="情报详情">
      <PageSection
        title={itemId}
        description="展示来源归属、风险评分、车辆域字段、评分解释和关联告警。"
      >
        <IntelligenceDetailPanel itemId={itemId} />
      </PageSection>
    </WorkbenchShell>
  );
}
