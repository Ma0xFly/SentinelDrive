---
title: SentinelDrive
---

# APM 任务追踪器

## 任务追踪

**Stage 1：** 已完成

**Stage 2：** 已完成

**Stage 3：** 已完成

**Stage 4：** 已完成

**Stage 5：** 已完成

**Stage 6：** 已完成

**Stage 7：** 已完成

**Stage 8：** 已完成

**Stage 9：** 已完成

**Stage 10：** 进行中

## Stage 10 任务追踪

| 任务 | 名称 | Agent | 状态 | 任务日志 |
| --- | --- | --- | --- | --- |
| 10.1 | 访客只读后端 | backend-agent | Active | `.apm/memory/stage-10/task-10-01.log.md` |
| 10.2 | 访客只读前端 | frontend-agent | Waiting: 10.1 | `.apm/memory/stage-10/task-10-02.log.md` |
| 10.3 | 垂直信源扩展（NHTSA + vendor） | intelligence-pipeline-agent | Active | `.apm/memory/stage-10/task-10-03.log.md` |
| 10.4 | 配置与文档同步 | qa-documentation-agent | Waiting: 10.2, 10.3 | `.apm/memory/stage-10/task-10-04.log.md` |

## Worker 追踪

| Agent | Instance | 备注 |
|-------|----------|------|
| platform-agent | 1 | |
| backend-agent | 1 | |
| intelligence-pipeline-agent | 1 | |
| frontend-agent | 1 | |
| qa-documentation-agent | 1 | |

## 版本控制

| Repository | Base Branch | Branch Convention | Commit Convention |
|-----------|-------------|-------------------|-------------------|
| SentinelDrive | main | `type/short-description` | `type: description`，允许 `feat`、`fix`、`refactor`、`docs`、`test`、`chore` |

## 工作备注

- Stage 10 范围（2026-09-08 与用户确认）：访客只读边界 = 情报列表/详情 + 信源非敏感字段 + 态势仪表盘可匿名读，一律只读；写操作、导出、告警处置、手工录入、用户管理、信源运维细节（任务日志/错误/计数）保持登录。信源扩展 = A 补 vendor 端点（Vector Informatik / Wind River / Geely / 小米，经实测可进）+ B 新增 NHTSA 召回 connector；通用威胁情报库搁置；AI 助手继续不做。
- NHTSA 召回归属 `incident`（软件/OTA 相关打 `recall`/`software_related` 标签，机械类采集层过滤）；vehicle 端点免 key，`recallsByMake/campaigns` 需认证不可用，车辆清单配置化；`Count=0` 宽容，VPIC 规范 model 名。
- 10.1/10.3 无相互依赖、改动文件不重叠（backend vs worker），并行派发；10.2 依赖 10.1，10.4 依赖 10.2+10.3。
