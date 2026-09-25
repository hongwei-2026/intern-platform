# CI 回归清单（踩坑固化）

本仓库 CI 把近期踩过的问题变成可自动失败的检查，避免「本地碰巧过、一刷新又炸」。

## API（`pytest`）

| 用例 | 防什么 |
|------|--------|
| `test_public_community_apis_strip_invite_code` | 公开列表/详情泄露邀请码 |
| `test_admin_of_returns_only_bound_community_with_invite` | 管理员一人一社；组织台才可见邀请码 |
| `test_committee_admin_of_empty_without_community_binding` | 组委会不被当成「全站社区管理员」 |
| `test_student_cannot_access_admin_of` | 学生越权读 admin-of |
| `test_mentor_register_with_private_invite_code` | 导师须正确邀请码自助注册 |
| `test_rejected_application_can_reapply` | 驳回后无法再次申请 |
| `test_community_admin_can_patch_homepage_fields` | 主页 PATCH 不落库 / 公开页仍带码 |

文件：`tests/test_regression_guards.py`

## Web（`apps/web`）

| 脚本 | 防什么 |
|------|--------|
| `npm run check:templates` | `<template>` 写 `as` / `!` → Vite 对 `.vue` 返回 500 |
| `npm run check:compile` | SFC 模板/脚本编译失败 |
| `npm run check:structure` | 公开主页塞管理功能、组织台回到三卡并排 |
| `npm run typecheck` | TS 类型错误 |
| `npm run build` | 生产构建失败 |

本地一键：`cd apps/web && npm run ci`

## GitHub Actions

`.github/workflows/ci.yml`：API job 跑全量 pytest；Web job 先跑三个 guard，再 typecheck + build。
