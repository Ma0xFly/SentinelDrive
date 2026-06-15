import { PageSection, WorkbenchShell } from "../components/WorkbenchShell";
import { AlertsWorkbench } from "./AlertsWorkbench";

export default function AlertsPage() {
  return (
    <WorkbenchShell active="/alerts" eyebrow="告警中心" title="告警">
      <PageSection
        title="告警队列"
        description="筛选、查看并更新后端告警状态；备注按后端 PATCH 规则保留或清除。"
      >
        <AlertsWorkbench />
      </PageSection>
    </WorkbenchShell>
  );
}
