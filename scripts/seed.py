#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""种子数据：演示账号 + 原有社区保留 + 追加真实开源案例社区。"""

from __future__ import annotations

import sys
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = Path(__file__).resolve().parent
for p in (SRC, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from intern_platform.db.session import SessionLocal  # noqa: E402
from intern_platform.models import (  # noqa: E402
    Application,
    Community,
    CommunityExtension,
    IntegrationSetting,
    Project,
    Role,
    User,
    UserRole,
)
from project_briefs import (  # noqa: E402
    AI_BRIEF,
    DEVTOOLS_BRIEF,
    DOCS_BRIEF,
    MIRROR_BRIEF,
    SPMV_BRIEF,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEMO_PASSWORD = "Demo@123456"

ROLES = [
    ("student", "学生"),
    ("mentor", "导师"),
    ("community_admin", "社区管理员"),
    ("committee", "组委会"),
]

DEMO_USERS = [
    {
        "email": "student@demo.hust.edu.cn",
        "display_name": "演示学生",
        "role_code": "student",
        "school": "华中科技大学",
    },
    {
        "email": "mentor@demo.hust.edu.cn",
        "display_name": "演示导师",
        "role_code": "mentor",
        "school": "华中科技大学",
    },
    {
        "email": "admin@demo.hust.edu.cn",
        "display_name": "演示社区管理员",
        "role_code": "community_admin",
        "school": "华中科技大学",
    },
    {
        "email": "committee@demo.hust.edu.cn",
        "display_name": "演示组委会",
        "role_code": "committee",
        "school": "华中科技大学",
    },
]

INTEGRATION_DEFAULTS = {
    "portal.home_url": "https://hust.openatom.club/",
    "portal.docs_url": "https://github.com/hust-open-atom-club/docs",
    "portal.join_guide_url": "https://hust.openatom.club/",
    "gitea.base_url": "https://git.hust.openatom.club/",
    "mirror.home_url": "https://mirrors.hust.edu.cn/",
    "auth.provider": "local",
    "db.note": "sqlite-default",
}

KERNEL_SCHEMA = (
    '{"type":"object","required":["resume_pdf","design_pdf"],'
    '"properties":{"resume_pdf":{"type":"string"},"design_pdf":{"type":"string"}}}'
)

MIRROR_SCHEMA = (
    '{"type":"object","required":["resume_pdf","design_pdf"],'
    '"properties":{"resume_pdf":{"type":"string"},"design_pdf":{"type":"string"},'
    '"mirror_sync_plan":{"type":"string"}}}'
)


def _ensure_role_binding(session, *, user_id: int, role: Role, community_id: int | None) -> None:
    if community_id is None:
        has_role = session.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.community_id.is_(None),
            )
        )
    else:
        has_role = session.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.community_id == community_id,
            )
        )
    if not has_role:
        session.add(UserRole(user_id=user_id, role_id=role.id, community_id=community_id))


def _upsert_community(
    session,
    *,
    slug: str,
    name: str,
    description: str,
    homepage_url: str,
    invite_code: str,
    logo_url: str | None = None,
    tags: str | None = None,
    gitea_org_url: str | None = None,
    mirror_doc_url: str | None = None,
    applicant_id: int | None = None,
    reviewed_by: int | None = None,
) -> Community:
    row = session.scalar(select(Community).where(Community.slug == slug))
    if not row:
        row = Community(
            name=name,
            slug=slug,
            description=description,
            homepage_url=homepage_url,
            gitea_org_url=gitea_org_url,
            mirror_doc_url=mirror_doc_url,
            logo_url=logo_url,
            tags=tags,
            status="approved",
            applicant_user_id=applicant_id,
            reviewed_by=reviewed_by,
            review_comment="演示通过",
            invite_code=invite_code,
        )
        session.add(row)
        session.flush()
    else:
        row.status = "approved"
        row.name = name
        row.description = description
        row.homepage_url = homepage_url
        row.gitea_org_url = gitea_org_url
        row.mirror_doc_url = mirror_doc_url
        row.logo_url = logo_url
        row.tags = tags
        row.invite_code = row.invite_code or invite_code
    return row


def _ensure_extension(session, community_id: int, schema: str) -> None:
    ext = session.scalar(
        select(CommunityExtension).where(CommunityExtension.community_id == community_id)
    )
    if not ext:
        session.add(
            CommunityExtension(
                community_id=community_id,
                application_schema=schema,
                enabled_modules='["applications","finals"]',
            )
        )
    else:
        ext.application_schema = schema


def _upsert_first_project(
    session,
    *,
    community_id: int,
    mentor_id: int,
    title: str,
    summary: str,
    description: str,
    tech_stack: str,
    difficulty: str,
    repo_url: str,
) -> Project:
    proj = session.scalar(
        select(Project).where(Project.community_id == community_id).order_by(Project.id.asc())
    )
    if not proj:
        proj = Project(
            community_id=community_id,
            mentor_id=mentor_id,
            title=title,
            summary=summary,
            description=description,
            tech_stack=tech_stack,
            difficulty=difficulty,
            quota=2,
            repo_url=repo_url,
            status="published",
        )
        session.add(proj)
        session.flush()
    else:
        proj.title = title
        proj.summary = summary
        proj.description = description
        proj.tech_stack = tech_stack
        proj.difficulty = difficulty
        proj.repo_url = repo_url
        proj.mentor_id = mentor_id
        proj.status = "published"
    return proj


def seed() -> None:
    password_hash = pwd_context.hash(DEMO_PASSWORD)
    session = SessionLocal()
    try:
        role_by_code: dict[str, Role] = {}
        for code, name in ROLES:
            existing = session.scalar(select(Role).where(Role.code == code))
            if existing:
                role_by_code[code] = existing
            else:
                role = Role(code=code, name=name)
                session.add(role)
                session.flush()
                role_by_code[code] = role

        user_by_role: dict[str, User] = {}
        for item in DEMO_USERS:
            existing = session.scalar(select(User).where(User.email == item["email"]))
            if existing:
                user = existing
            else:
                user = User(
                    email=item["email"],
                    password_hash=password_hash,
                    display_name=item["display_name"],
                    school=item["school"],
                    auth_provider="local",
                )
                session.add(user)
                session.flush()
            user_by_role[item["role_code"]] = user
            _ensure_role_binding(
                session,
                user_id=user.id,
                role=role_by_code[item["role_code"]],
                community_id=None,
            )

        admin = user_by_role["community_admin"]
        mentor = user_by_role["mentor"]
        committee = user_by_role["committee"]
        student = user_by_role["student"]

        # ----- 原有演示社区（保留） -----
        community = _upsert_community(
            session,
            slug="kernel",
            name="内核社区",
            description="聚焦操作系统内核、驱动与性能相关开源课题，适合系统方向同学深入实践。",
            homepage_url="https://hust.openatom.club/",
            invite_code="KERNEL-DEMO",
            logo_url="/logos/kernel.svg",
            tags='["操作系统","驱动","C语言"]',
            applicant_id=admin.id,
            reviewed_by=committee.id,
        )
        _ensure_role_binding(
            session, user_id=admin.id, role=role_by_code["community_admin"], community_id=community.id
        )
        _ensure_role_binding(
            session, user_id=mentor.id, role=role_by_code["mentor"], community_id=community.id
        )
        _ensure_role_binding(
            session, user_id=mentor.id, role=role_by_code["mentor"], community_id=None
        )
        _ensure_extension(session, community.id, KERNEL_SCHEMA)
        project = _upsert_first_project(
            session,
            community_id=community.id,
            mentor_id=mentor.id,
            title="SpMV 开源实习演示项目",
            summary="稀疏矩阵向量乘开源贡献演示，打通申请到结项全链路",
            description=SPMV_BRIEF,
            tech_stack='["C语言","Python"]',
            difficulty="medium",
            repo_url="https://git.hust.openatom.club/demo/spmv",
        )
        app = session.scalar(
            select(Application).where(
                Application.project_id == project.id,
                Application.student_id == student.id,
            )
        )
        if not app:
            session.add(
                Application(
                    project_id=project.id,
                    student_id=student.id,
                    statement="希望参与开源实习演示。",
                    status="draft",
                    current_node="none",
                    version=0,
                )
            )

        mirror = _upsert_community(
            session,
            slug="mirror",
            name="镜像运维社区",
            description="围绕校园镜像站与软件源运维，训练同步策略、监控与自动化能力。",
            homepage_url="https://mirrors.hust.edu.cn/",
            mirror_doc_url="https://mirrors.hust.edu.cn/",
            invite_code="MIRROR-DEMO",
            logo_url="/logos/hust-mirror.svg",
            tags='["镜像","运维开发","Shell脚本"]',
            applicant_id=admin.id,
            reviewed_by=committee.id,
        )
        _ensure_extension(session, mirror.id, MIRROR_SCHEMA)
        _upsert_first_project(
            session,
            community_id=mirror.id,
            mentor_id=admin.id,
            title="镜像同步策略优化",
            summary="优化镜像同步策略并演示社区专属申请字段",
            description=MIRROR_BRIEF,
            tech_stack='["Shell脚本","Python"]',
            difficulty="easy",
            repo_url="https://git.hust.openatom.club/demo/mirror",
        )

        all_more = [
            # 原有额外社区
            {
                "slug": "docs",
                "name": "技术文档社区",
                "description": "面向开源文档、教程与本地化贡献，适合写作与知识整理方向的同学。",
                "homepage_url": "https://hust.openatom.club/",
                "invite_code": "DOCS-DEMO",
                "logo_url": "/logos/docs.svg",
                "tags": '["文档","Markdown","Git"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "俱乐部贡献指南改版",
                    "summary": "梳理新人入门路径与仓库贡献规范",
                    "description": DOCS_BRIEF,
                    "tech_stack": '["Markdown","Git"]',
                    "difficulty": "easy",
                    "repo_url": "https://git.hust.openatom.club/demo/docs",
                },
            },
            {
                "slug": "devtools",
                "name": "开发者工具社区",
                "description": "围绕 CI、脚本、脚手架与工程效率工具，承接可落地的工程化实习课题。",
                "homepage_url": "https://hust.openatom.club/",
                "invite_code": "TOOLS-DEMO",
                "logo_url": "/logos/devtools.svg",
                "tags": '["运维开发","Shell脚本","Docker"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "实习平台本地一键启动脚本",
                    "summary": "封装环境检查与服务拉起流程",
                    "description": DEVTOOLS_BRIEF,
                    "tech_stack": '["Python","Shell脚本","Docker"]',
                    "difficulty": "medium",
                    "repo_url": "https://git.hust.openatom.club/demo/devtools",
                },
            },
            {
                "slug": "ai-lab",
                "name": "AI 开源实验室",
                "description": "探索开源模型推理、评测与轻量应用落地，适合有一定 Python / 机器学习基础的同学。",
                "homepage_url": "https://hust.openatom.club/",
                "invite_code": "AILAB-DEMO",
                "logo_url": "/logos/ailab.svg",
                "tags": '["人工智能","深度学习","Python"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "开源模型推理示例工程",
                    "summary": "打通本地推理演示与文档",
                    "description": AI_BRIEF,
                    "tech_stack": '["Python","PyTorch"]',
                    "difficulty": "hard",
                    "repo_url": "https://git.hust.openatom.club/demo/ai-lab",
                },
            },
            # 新增开源案例（新 slug，不覆盖上面）
            {
                "slug": "openeuler",
                "name": "openEuler 社区",
                "description": "openEuler 是开放原子开源基金会旗下的开源操作系统，面向数字基础设施，适合系统与内核方向实践。",
                "homepage_url": "https://www.openeuler.org/zh/",
                "gitea_org_url": "https://gitee.com/openeuler",
                "invite_code": "EULER-DEMO",
                "logo_url": "/logos/openeuler.svg",
                "tags": '["操作系统","编译器","嵌入式"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "稀疏矩阵向量乘（SpMV）算子优化",
                    "summary": "基于开源数值计算方向，完成 SpMV 性能优化与文档沉淀",
                    "description": SPMV_BRIEF,
                    "tech_stack": '["C语言","Python"]',
                    "difficulty": "medium",
                    "repo_url": "https://gitee.com/openeuler",
                },
            },
            {
                "slug": "opengauss",
                "name": "openGauss 社区",
                "description": "openGauss 是面向企业级场景的开源关系型数据库，适合数据库内核、工具与文档方向贡献。",
                "homepage_url": "https://opengauss.org/zh/",
                "gitea_org_url": "https://gitee.com/opengauss",
                "invite_code": "GAUSS-DEMO",
                "logo_url": "/logos/opengauss.svg",
                "tags": '["数据库","运维开发","C语言"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "openGauss 新手贡献指南整理",
                    "summary": "梳理仓库贡献规范、本地编译与文档索引",
                    "description": DOCS_BRIEF,
                    "tech_stack": '["Markdown","Git","文档"]',
                    "difficulty": "easy",
                    "repo_url": "https://gitee.com/opengauss",
                },
            },
            {
                "slug": "mindspore",
                "name": "昇思 MindSpore",
                "description": "昇思 MindSpore 是面向全场景的开源深度学习框架，适合人工智能算法与工程化实习课题。",
                "homepage_url": "https://www.mindspore.cn/",
                "gitea_org_url": "https://gitee.com/mindspore",
                "invite_code": "MS-DEMO",
                "logo_url": "/logos/mindspore.svg",
                "tags": '["人工智能","深度学习","Python"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "昇思框架推理示例补全",
                    "summary": "基于昇思框架打通本地推理演示与说明文档",
                    "description": AI_BRIEF,
                    "tech_stack": '["Python","人工智能"]',
                    "difficulty": "hard",
                    "repo_url": "https://gitee.com/mindspore",
                },
            },
            {
                "slug": "rtthread",
                "name": "RT-Thread 社区",
                "description": "RT-Thread 是国产开源实时操作系统，面向物联网与嵌入式设备，适合驱动与组件开发实践。",
                "homepage_url": "https://www.rt-thread.org/",
                "gitea_org_url": "https://gitee.com/rtthread",
                "invite_code": "RTT-DEMO",
                "logo_url": "/logos/rtthread.svg",
                "tags": '["实时操作系统","嵌入式","C语言"]',
                "schema": KERNEL_SCHEMA,
                "project": {
                    "title": "RT-Thread 组件文档与示例补全",
                    "summary": "完善组件使用说明并补充最小可运行示例",
                    "description": DEVTOOLS_BRIEF,
                    "tech_stack": '["C语言","嵌入式","文档"]',
                    "difficulty": "medium",
                    "repo_url": "https://gitee.com/rtthread",
                },
            },
        ]

        for item in all_more:
            row = _upsert_community(
                session,
                slug=item["slug"],
                name=item["name"],
                description=item["description"],
                homepage_url=item["homepage_url"],
                invite_code=item["invite_code"],
                logo_url=item.get("logo_url"),
                tags=item.get("tags"),
                gitea_org_url=item.get("gitea_org_url"),
                applicant_id=admin.id,
                reviewed_by=committee.id,
            )
            _ensure_extension(session, row.id, item.get("schema") or KERNEL_SCHEMA)
            meta = item["project"]
            _upsert_first_project(
                session,
                community_id=row.id,
                mentor_id=admin.id,
                title=meta["title"],
                summary=meta["summary"],
                description=meta["description"],
                tech_stack=meta["tech_stack"],
                difficulty=meta["difficulty"],
                repo_url=meta["repo_url"],
            )

        # 演示社区管理员仅保留「内核社区」管理权
        extras = session.scalars(
            select(UserRole).where(
                UserRole.user_id == admin.id,
                UserRole.role_id == role_by_code["community_admin"].id,
                UserRole.community_id.is_not(None),
                UserRole.community_id != community.id,
            )
        ).all()
        for ur in extras:
            session.delete(ur)

        # 演示导师只挂内核社区
        mentor_extras = session.scalars(
            select(UserRole).where(
                UserRole.user_id == mentor.id,
                UserRole.role_id == role_by_code["mentor"].id,
                UserRole.community_id.is_not(None),
                UserRole.community_id != community.id,
            )
        ).all()
        for ur in mentor_extras:
            session.delete(ur)

        # 隐藏自动化冒烟组织，不进入公开列表
        for smoke in session.scalars(
            select(Community).where(Community.slug.like("smoke-%"))
        ).all():
            smoke.status = "rejected"

        for key, value in INTEGRATION_DEFAULTS.items():
            existing = session.get(IntegrationSetting, key)
            if existing is None:
                session.add(IntegrationSetting(key=key, value=value))

        session.commit()
        print("Seed OK")
        print(f"  password for all demo users: {DEMO_PASSWORD}")
        for item in DEMO_USERS:
            print(f"  - {item['role_code']}: {item['email']}")
        names = session.scalars(
            select(Community.slug).where(Community.status == "approved").order_by(Community.id)
        ).all()
        print(f"  communities: {', '.join(names)}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
