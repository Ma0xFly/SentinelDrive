import { PageSection, WorkbenchShell } from "../components/WorkbenchShell";
import { UserWorkbench } from "./UserWorkbench";

export default function UserPage() {
  return (
    <WorkbenchShell active="/user" eyebrow="用户基础" title="用户基础">
      <PageSection
        title="当前用户与基础管理"
        description="展示当前登录用户；管理员可创建用户并启停基础账号。"
      >
        <UserWorkbench />
      </PageSection>
    </WorkbenchShell>
  );
}
