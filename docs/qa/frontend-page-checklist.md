# 前端页面 Checklist

## 当前工作台

- [ ] `/` 受登录状态保护。
- [ ] `/intelligence/[id]` 可展示情报详情、source attribution、风险评分和导出动作。
- [ ] `/alerts` 可展示告警列表、详情和状态更新。
- [ ] `/sources` 可展示 source status、job logs 和 processing controls。
- [ ] `/manual-entry` 可提交人工录入，并显示校验错误。
- [ ] `/user` 可展示当前用户和基础用户管理能力。

## 可用性

- [ ] UI 文案默认中文。
- [ ] 页面是安全运营工作台风格，不是营销页。
- [ ] Loading、error、empty 和 session-expired 状态清晰。
- [ ] 长文本、风险标签、状态标签和按钮不会重叠。
- [ ] 非管理员用户的 admin-only 控件在前端禁用，后端仍强制授权。

## 用户流程

- [ ] Playwright workflow 覆盖登录保护访问。
- [ ] Playwright workflow 覆盖 intelligence list/detail/export。
- [ ] Playwright workflow 覆盖 manual-entry validation/submission。
- [ ] Playwright workflow 覆盖 source processing controls 和 alert evaluation。
- [ ] Playwright workflow 覆盖 alert status update。

## 敏感数据

- [ ] 前端不展示 raw payloads、collector headers、Token、API keys、cookies 或 passwords。
- [ ] Export download 使用认证 helper，不使用裸 URL。
- [ ] `NEXT_PUBLIC_` 变量不包含密钥或内部私有地址。
