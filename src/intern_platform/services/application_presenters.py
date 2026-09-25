"""申请序列化：附带项目标题、学生信息、PDF 材料与审核流水。"""

from __future__ import annotations

import json
from typing import Any

from intern_platform.models.application import Application
from intern_platform.schemas.business import ApplicationOut


def _parse_extra(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _pdf_fields(app: Application) -> tuple[str | None, str | None]:
    extra = _parse_extra(app.extra_fields)
    resume = extra.get("resume_pdf") or app.attachment_url
    design = extra.get("design_pdf")
    return (
        str(resume) if resume else None,
        str(design) if design else None,
    )


def application_to_out(app: Application) -> ApplicationOut:
    records = []
    for r in getattr(app, "review_records", None) or []:
        records.append(
            {
                "id": r.id,
                "seq_no": getattr(r, "seq_no", None),
                "from_status": r.from_status,
                "to_status": r.to_status,
                "action": r.action,
                "decision_code": getattr(r, "decision_code", None),
                "actor_id": getattr(r, "actor_id", None),
                "actor_role": getattr(r, "actor_role", None),
                "comment": getattr(r, "comment", None),
                "created_at": getattr(r, "created_at", None),
            }
        )
    project = getattr(app, "project", None)
    student = getattr(app, "student", None)
    resume_pdf, design_pdf = _pdf_fields(app)
    student_name = None
    student_email = None
    if student is not None:
        student_email = student.email
        name = (student.display_name or "").strip()
        # 避免展示占位名「学生」「演示学生」时优先用邮箱前缀 / 简历文件名推断
        if name and name not in ("学生", "演示学生") and not name.startswith("学生"):
            student_name = name
        elif student.email:
            student_name = student.email.split("@", 1)[0]
        else:
            student_name = name or None
    if not student_name and resume_pdf:
        # 从「于鸿伟-简历.pdf」类文件名提取姓名
        try:
            from urllib.parse import unquote

            base = unquote(str(resume_pdf).rsplit("/", 1)[-1])
            base = base.split("_", 1)[-1] if len(base) > 13 and "_" in base[:13] else base
            guess = base.replace(".pdf", "").replace(".PDF", "")
            for suf in ("-简历", "_简历", "简历", "-resume", "_resume", "-Resume"):
                if suf in guess:
                    guess = guess.split(suf)[0]
                    break
            guess = guess.strip("-_ ")
            if guess and len(guess) <= 32:
                student_name = guess
        except Exception:  # noqa: BLE001
            pass

    return ApplicationOut(
        id=app.id,
        project_id=app.project_id,
        student_id=app.student_id,
        student_name=student_name,
        student_email=student_email,
        statement=app.statement,
        attachment_url=app.attachment_url,
        extra_fields=app.extra_fields,
        resume_pdf=resume_pdf,
        design_pdf=design_pdf,
        status=app.status,
        current_node=app.current_node,
        version=app.version,
        project_title=project.title if project is not None else None,
        review_records=records or None,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )
