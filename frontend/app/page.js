import { PageSection, WorkbenchShell } from "./components/WorkbenchShell";
import { IntelligenceWorkbench } from "./intelligence/IntelligenceWorkbench";

export default function Home() {
  return (
    <WorkbenchShell active="/" eyebrow="情报工作台" title="情报列表">
      <PageSection
        title="情报检索"
        description="按 CVE、厂商、组件、攻击面、来源、风险和状态筛选归一化情报。"
      >
        <IntelligenceWorkbench />
      </PageSection>
    </WorkbenchShell>
  );
}
