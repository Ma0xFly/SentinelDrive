# 中文开发基线迁移记录

## 背景

2026-06-15，项目切换为以 `D:\桌面\SentinelDrive-cn` 作为中文开发基线继续推进。该目录在 WSL 中对应 `/mnt/d/桌面/SentinelDrive-cn`。

检查结果：

- 当前工作区 `/home/myx/SentinelDrive` 保留完整 Stage 1-7 Git 历史，迁移前 HEAD 为 `0673ac5`。
- 中文版本 `SentinelDrive-cn` 是独立 Git 历史，HEAD 为 `56447cf`。
- 两边核心业务代码一致；中文版本主要提供中文 README、文档、AGENTS 规则和 APM 上下文。

## 迁移策略

不要直接用 `SentinelDrive-cn` 整目录覆盖当前仓库，也不要替换 `.git`。当前仓库继续作为主工作区，保留既有 Git 历史和 Stage 1-7 提交线索。

同步时采用以下原则：

- 同步中文版本中的项目源码、README、docs、APM 上下文和需求文档。
- 排除 `.git/`，避免替换当前仓库历史。
- 排除 `.env`、`.venv`、`node_modules`、缓存、构建产物、Playwright 产物和备份目录。
- `.agents/` 与 `.codex/` 是本地 APM/Codex 工具目录，可能为只读挂载；不把工具目录替换作为业务迁移前提。
- 从 Windows 文件系统同步后，需要检查并修正普通文件可执行权限，避免无意义 mode change。

## 后续阶段

迁移后新增 Stage 8：前端适配与 AI 情报接入预留。

Stage 8 目标：

- 修复情报页面和来源管理页面在浏览器中的宽度、遮挡、溢出和响应式问题。
- 为后续 AI 定时采集器预留认证后的外部情报 ingest API。
- 将 AI/外部来源数据纳入既有 raw intelligence、normalization、deduplication、scoring 和 source attribution 流程。
- 更新测试和文档，明确已实现接口和仅预留扩展点。
