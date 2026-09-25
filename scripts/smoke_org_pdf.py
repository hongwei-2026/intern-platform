"""Quick smoke: profile save, PDF upload/apply, org settle/join."""
from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8000/api/v1"
ROOT = Path(__file__).resolve().parents[1]


def req(method: str, path: str, data=None, token=None, files=None):
    url = BASE + path
    headers: dict[str, str] = {
        "X-Idempotency-Key": str(uuid.uuid4()),
        "X-Request-ID": str(uuid.uuid4()),
    }
    body = None
    if files:
        name, content, ctype = files
        boundary = "----bound" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def main() -> None:
    st, login = req(
        "POST",
        "/auth/login",
        {"email": "student@demo.hust.edu.cn", "password": "Demo@123456"},
    )
    assert st == 200, login
    tok = login["access_token"]
    st, me = req("PATCH", "/auth/me", {"display_name": "演示学生", "bio": "smoke"}, tok)
    print("save", st, me.get("display_name") if isinstance(me, dict) else me)

    pdf = (ROOT / "data/samples/project-design-template.pdf").read_bytes()
    st, u1 = req("POST", "/uploads/pdf", token=tok, files=("resume.pdf", pdf, "application/pdf"))
    st2, u2 = req("POST", "/uploads/pdf", token=tok, files=("design.pdf", pdf, "application/pdf"))
    print("upload", st, st2)
    assert st == 200 and st2 == 200, (u1, u2)

    # 优先找尚未申请过的项目
    st, projects = req("GET", "/projects")
    project_id = 2
    if isinstance(projects, list) and projects:
        project_id = projects[0]["id"]
        st_mine, mine_apps = req("GET", "/applications/mine", token=tok)
        applied = set()
        if isinstance(mine_apps, list):
            applied = {a.get("project_id") for a in mine_apps}
        for p in projects:
            if p["id"] not in applied:
                project_id = p["id"]
                break

    st, app = req(
        "POST",
        f"/projects/{project_id}/applications",
        {
            "statement": "smoke apply",
            "attachment_url": u1["url"],
            "extra_fields": {"resume_pdf": u1["url"], "design_pdf": u2["url"]},
            "submit": True,
        },
        tok,
    )
    print("apply", st, app if not isinstance(app, dict) else (app.get("id"), app.get("status")))

    st, al = req(
        "POST",
        "/auth/login",
        {"email": "admin@demo.hust.edu.cn", "password": "Demo@123456"},
    )
    atok = al["access_token"]
    slug = f"smoke-org-{random.randint(1000, 9999)}"
    st, org = req(
        "POST",
        "/communities",
        {"name": "新测试社区", "slug": slug, "description": "入驻"},
        atok,
    )
    print("org", st, org if not isinstance(org, dict) else (org.get("id"), org.get("status")))
    assert st in (200, 201), org

    st, cl = req(
        "POST",
        "/auth/login",
        {"email": "committee@demo.hust.edu.cn", "password": "Demo@123456"},
    )
    ctok = cl["access_token"]
    st, rev = req(
        "POST",
        f"/communities/{org['id']}/review",
        {"decision": "approve", "comment": "ok"},
        ctok,
    )
    print(
        "approve",
        st,
        rev if not isinstance(rev, dict) else (rev.get("invite_code"), rev.get("status")),
    )
    assert st == 200 and rev.get("invite_code"), rev

    st, ml = req(
        "POST",
        "/auth/login",
        {"email": "mentor@demo.hust.edu.cn", "password": "Demo@123456"},
    )
    mtok = ml["access_token"]
    st, join = req(
        "POST",
        "/communities/join",
        {"invite_code": rev["invite_code"], "as_role": "mentor"},
        mtok,
    )
    print("join", st, join)
    st, mine = req("GET", "/communities/mine", token=mtok)
    print(
        "mine",
        st,
        [(x.get("slug"), x.get("invite_code")) for x in mine]
        if isinstance(mine, list)
        else mine,
    )


if __name__ == "__main__":
    main()
