import { PageSection, WorkbenchShell } from "../components/WorkbenchShell";
import { ManualEntryWorkbench } from "./ManualEntryWorkbench";

export default function ManualEntryPage() {
  return (
    <WorkbenchShell active="/manual-entry" eyebrow="人工录入" title="人工录入">
      <PageSection
        title="录入与维护"
        description="提交人工录入条目，支持常用漏洞、公告、事件、暴露面和研究线索字段。"
      >
        <ManualEntryWorkbench />
      </PageSection>
    </WorkbenchShell>
  );
}
