# 开源实习平台 · Web 前端

Vue 3 + Vite + Vue Router + Pinia，对接本地 API `http://127.0.0.1:8000`（经 Vite 代理 `/api`）。

## 启动

```bash
cd apps/web
npm install
npm run dev
```

开发服务器默认端口 **5173**，浏览器访问：http://127.0.0.1:5173

请先启动后端（默认 `http://127.0.0.1:8000`），前端通过 `vite.config.ts` 将 `/api` 代理到该地址。

## 功能概览

- 首页：介绍 + `GET /api/v1/integrations/links` 门户外链
- 登录 / 注册（`/auth/login`、`/auth/register`）
- 社区列表与详情（含扩展信息，需权限）
- 项目列表与详情（申请表单，支持 `extra_fields` JSON）
- 公示列表
- 学生：我的申请、申请详情（留言 / 提交 / 结项）
- 导师：创建与发布项目、按申请 ID 审核
- 社区管理员：按申请 ID 审核
- 组委会：待审社区、申请审核、发布公示

鉴权 Token 存于 `localStorage`；角色工作台路由仅做登录校验（软守卫）。
