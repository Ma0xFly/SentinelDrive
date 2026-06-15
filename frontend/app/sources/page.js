import { PageSection, WorkbenchShell } from "../components/WorkbenchShell";
import { SourcesWorkbench } from "./SourcesWorkbench";

export default function SourcesPage() {
  return (
    <WorkbenchShell active="/sources" eyebrow="来源状态" title="来源管理">
      <PageSection
        title="来源清单"
        description="查看来源同步健康度、最近任务、失败原因，并更新后端支持的来源状态。"
      >
        <SourcesWorkbench />
      </PageSection>
    </WorkbenchShell>
  );
}
