# 华科开放原子开源实习管理系统 — 后端

面向华中科技大学开放原子俱乐部的开源实习管理后端（任务 2/3）。

## 技术栈

- FastAPI + Pydantic v2 + JWT（python-jose）+ bcrypt（passlib）
- SQLAlchemy 2.0 + Alembic；默认 SQLite（`data/intern.db`）
- 企业级 APPEND-ONLY 流水：`review_records` / `audit_logs` / `workflow_events`
- 申请状态机仅经 `ApplicationWorkflowService`；业务审核经 `ReviewUseCase`

## 目录结构

```text
intern-platform/
  apps/api/main.py
  src/intern_platform/
    api/routes/          # auth/communities/projects/applications/reviews/...
    dependencies/        # JWT RBAC + ledger 请求上下文
    services/            # 状态机、工作流、审核用例、业务服务
    models/ + repositories/
    integration/portal.py
  alembic/versions/      # 0001 → 0002 ledger → 0003 task3
  scripts/seed.py
  tests/
```

## 快速开始

```bash
cd intern-platform
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
copy .env.example .env

alembic upgrade head
python scripts/seed.py
```

### 日常开发 / 给学校演示（推荐）

**双击** `scripts/start-dev.bat`，或：

```powershell
.\scripts\start-dev.ps1
```

会拉起：

- 后端 <http://127.0.0.1:8001>（健康检查 `/api/v1/health`）
- 前端 <http://127.0.0.1:5173>（代理 `/api` → 8001）

只开前端、后端进程挂了时，浏览器里常表现为 **500 / 连不上**——不是业务代码坏了，是 API 没在跑。用上面的脚本可避免。

手动分别启动：

```bash
# 终端 1
uvicorn apps.api.main:app --reload --app-dir . --host 127.0.0.1 --port 8001

# 终端 2
cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173
```

- OpenAPI：<http://127.0.0.1:8001/docs>
- 健康检查：`GET /api/v1/health`
- CORS 已允许 `localhost:5173` / `3000`（可用 `CORS_ORIGINS` 覆盖）

## 演示账号

密码均为 `Demo@123456`：

| 角色 | 邮箱 |
|------|------|
| student | student@demo.hust.edu.cn |
| mentor | mentor@demo.hust.edu.cn |
| community_admin | admin@demo.hust.edu.cn |
| committee | committee@demo.hust.edu.cn |

种子含社区 `kernel` / `mirror`（不同 `application_schema`）、已发布项目与一条 draft 申请。

## 主要 API（`/api/v1`）

| 模块 | 路径前缀 |
|------|----------|
| 鉴权 | `/auth/register` `/login` `/me` |
| 社区 | `/communities` `/{slug}` `/{id}/review` `/{id}/extension` |
| 项目 | `/projects` `/{id}/publish` `/{id}/applications` |
| 申请 | `/applications/mine` `/{id}` `/{id}/submit` `/{id}/transitions` |
| 审核 | `/applications/{id}/reviews` |
| 公示 | `/announcements` |
| 结项 | `/applications/{id}/final` `/final/submit` `/final/reviews` |
| 留言 | `/applications/{id}/messages` |
| 门户 | `/integrations/links` |

### 企业级流水约定

- 成功写路径（审核 / transitions / submit 等）**必须**带 `X-Idempotency-Key`（缺则 400）
- `X-Request-ID` / `X-Trace-ID` 可省略，服务端自动生成并回写响应头与流水
- `actor_role` 取自服务端鉴权角色，不信任客户端 Header
- `applications.version` 乐观锁：可传 `version`，冲突返回 409 并写 FAIL 审计
- 社区审核 / 项目发布 / 公示发布写 `audit_logs` SUCCESS（社区/项目另写 `workflow_events`）

## 示例：登录 → 提交 → 导师审核

```bash
# 登录
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@demo.hust.edu.cn","password":"Demo@123456"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 学生提交申请（假设 id=1）
curl -s -X POST http://127.0.0.1:8000/api/v1/applications/1/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Idempotency-Key: $(python -c 'import uuid; print(uuid.uuid4())')"

# 导师审核通过
MENTOR=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"mentor@demo.hust.edu.cn","password":"Demo@123456"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://127.0.0.1:8000/api/v1/applications/1/reviews \
  -H "Authorization: Bearer $MENTOR" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: $(python -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"decision":"approve","comment":"LGTM"}'
```

## 状态机与审计

```text
draft → submitted → mentor_review → community_review → committee_review
  → selected | rejected
selected → in_progress → final_submitted
  → mentor_final_review → committee_final_review
  → completed | final_rejected
```

校验审计链：

```python
from intern_platform.db.session import SessionLocal
from intern_platform.services.ledger import verify_audit_chain

with SessionLocal() as s:
    print(verify_audit_chain(s))
```

## 测试

```bash
pip install -e ".[dev]"
pytest -q
```

覆盖：状态机单测、哈希链、任务3主链路（draft→completed）、幂等回放、非法迁移 FAIL 审计、越权 403；以及资料保存、PDF 上传/申请校验、组织入驻审批、组织码加入与 `/communities/mine`。

CI（GitHub Actions）：`api` 跑 pytest + alembic `invite_code` 迁移校验 + 生成项目设计 PDF；`web` 跑 `vue-tsc` 与生产构建。

## 数据库切换

见 `.env.example`（`DB_DRIVER` + `DATABASE_URL`）。业务代码走 ORM/Repository，不写方言 SQL。
