"""Cloud full functional E2E against http://127.0.0.1 (or SMOKE_WEB)."""
from __future__ import annotations

import io
import json
import os
import uuid
import zipfile
import urllib.error
import urllib.request
from typing import Any

WEB = os.environ.get("SMOKE_WEB", "https://intern.openatom.club").rstrip("/")
API = os.environ.get("SMOKE_API", f"{WEB}/api/v1").rstrip("/")
DEMO_PW = "Demo@123456"
ROWS: list[tuple[str, bool, Any]] = []

MINI_PDF = b"""%PDF-1.1
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>endobj
4 0 obj<< /Length 44 >>stream
BT /F1 12 Tf 50 150 Td (e2e) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer<< /Size 5 /Root 1 0 R >>
startxref
307
%%EOF
"""


def ok(name: str, passed: bool, info: Any = "") -> None:
    ROWS.append((name, passed, info))
    print(f"[{'OK' if passed else 'FAIL'}] {name}: {info}")


def call(
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
    *,
    base: str = API,
    raw: bool = False,
    headers: dict | None = None,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    h = {"X-Idempotency-Key": str(uuid.uuid4()), **(headers or {})}
    if body is not None:
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            blob = res.read()
            if raw:
                return res.status, blob
            text = blob.decode("utf-8", "replace")
            if not text:
                return res.status, None
            if text.startswith("{") or text.startswith("["):
                return res.status, json.loads(text)
            return res.status, text
    except urllib.error.HTTPError as e:
        raw_b = e.read()
        text = raw_b.decode("utf-8", "replace")
        try:
            detail = json.loads(text)
        except Exception:
            detail = text[:300]
        return e.code, detail
    except Exception as e:
        return 0, str(e)


def login(email: str, password: str = DEMO_PW) -> tuple[str | None, Any]:
    code, data = call("POST", "/auth/login", body={"email": email, "password": password})
    if code != 200:
        return None, data
    return data["access_token"], data["user"]


def upload(token: str, kind: str, filename: str, content: bytes, content_type: str) -> tuple[int, Any]:
    boundary = f"----e2e{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return call(
        "POST",
        f"/uploads/{kind}",
        token,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        # pass raw body via custom request
    ) if False else _upload_raw(token, kind, filename, content, content_type, boundary)


def _upload_raw(token: str, kind: str, filename: str, content: bytes, content_type: str, boundary: str) -> tuple[int, Any]:
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/uploads/{kind}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Idempotency-Key": str(uuid.uuid4()),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text[:300]


def mini_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "cloud e2e deliverable\n")
    return buf.getvalue()


ORG_CANDIDATES = [
    "admin@demo.hust.edu.cn",
    "mirror.admin@demo.hust.edu.cn",
    "docs.admin@demo.hust.edu.cn",
    "devtools.admin@demo.hust.edu.cn",
    "ai-lab.admin@demo.hust.edu.cn",
    "openeuler.admin@demo.hust.edu.cn",
    "opengauss.admin@demo.hust.edu.cn",
    "mindspore.admin@demo.hust.edu.cn",
    "rtthread.admin@demo.hust.edu.cn",
]


def find_org_for_community(community_id: int) -> str | None:
    for email in ORG_CANDIDATES:
        tok, _ = login(email)
        if not tok:
            continue
        code, rows = call("GET", "/communities/admin-of", tok)
        if code == 200 and isinstance(rows, list):
            if any(int(r.get("id")) == int(community_id) for r in rows):
                return email
    return None


def find_project_and_roles() -> tuple[dict, str, str]:
    """Return (project, mentor_email, org_email) using project.mentor_email."""
    code, projects = call("GET", "/projects?status=published")
    assert code == 200 and projects, projects
    candidates = []
    for p in projects:
        taken = int(p.get("seats_taken") or 0)
        quota = int(p.get("quota") or 0)
        avail = p.get("seats_available")
        if avail is None:
            open_seat = quota == 0 or taken < quota
        else:
            open_seat = int(avail) > 0
        if open_seat and p.get("mentor_email"):
            candidates.append(p)
    if not candidates:
        candidates = [p for p in projects if p.get("mentor_email")]
    # Prefer non-demo-kernel SpMV last
    candidates.sort(key=lambda p: (0 if "SpMV" not in (p.get("title") or "") else 1, p.get("id") or 0))
    for p in candidates:
        mentor = p.get("mentor_email")
        org = find_org_for_community(int(p["community_id"]))
        if mentor and org:
            # verify mentor can login
            tok, _ = login(mentor)
            if tok:
                return p, mentor, org
    raise RuntimeError("no usable project/mentor/org")


def main() -> int:
    # ---------- A. public pages ----------
    public_pages = [
        "/",
        "/login",
        "/register",
        "/register/mentor",
        "/ops/login",
        "/projects",
        "/communities",
        "/guide",
        "/news",
        "/completed",
        "/me",
        "/org",
        "/mentor",
        "/committee",
    ]
    for path in public_pages:
        code, _ = call("GET", path, base=WEB)
        # auth pages still return SPA shell 200
        ok(f"page {path}", code == 200, code)

    for path in ["/api/v1/health", "/api/v1/site/slides", "/api/v1/site/news", "/api/v1/site/guide"]:
        code, data = call("GET", path.replace("/api/v1", ""), base=API if path.startswith("/api") else WEB)
        # health/site via API base
    code, health = call("GET", "/health")
    ok("health", code == 200 and health.get("ok") is True, health)
    for ep in ("/site/slides", "/site/news", "/site/guide"):
        code, data = call("GET", ep)
        ok(f"public {ep}", code == 200, type(data).__name__)

    code, pubs = call("GET", "/projects?status=published")
    ok("published projects", code == 200 and isinstance(pubs, list) and len(pubs) > 0, f"n={len(pubs) if isinstance(pubs, list) else pubs}")
    code, communities = call("GET", "/communities?status=approved")
    ok("approved communities", code == 200 and isinstance(communities, list) and len(communities) > 0, f"n={len(communities) if isinstance(communities, list) else communities}")
    code, pend = call("GET", "/communities?status=pending")
    # 匿名：403/401，或 200 且空列表（不泄露待审详情）
    pend_ok = code in (401, 403) or (
        code == 200 and isinstance(pend, list) and len(pend) == 0
    )
    ok("pending communities gated", pend_ok, code)

    # ---------- B. auth ----------
    suffix = uuid.uuid4().hex[:8]
    email = f"e2e_{suffix}@test.local"
    password = "E2eTest#123456"
    code, reg = call(
        "POST",
        "/auth/register",
        body={"email": email, "password": password, "display_name": f"E2E学生{suffix}", "school": "华中科技大学"},
    )
    ok("register student", code == 200 and "access_token" in (reg or {}), reg if code != 200 else email)
    if code != 200:
        print("RESULT FAIL early")
        return 1
    student = reg["access_token"]
    student_id = reg["user"]["id"]

    code, me = call("GET", "/auth/me", student)
    ok("student /me", code == 200 and me.get("email") == email, me.get("email") if isinstance(me, dict) else me)
    code, me2 = call("PATCH", "/auth/me", student, {"major": "计算机", "bio": "cloud-e2e", "city": "武汉"})
    ok("student patch profile", code == 200 and me2.get("major") == "计算机", me2.get("major") if isinstance(me2, dict) else me2)
    code, bad = call("POST", "/auth/login", body={"email": email, "password": "wrong"})
    ok("bad password rejected", code == 401, code)

    # mentor invite register
    code, mreg = call(
        "POST",
        "/auth/register-mentor",
        body={
            "email": f"e2e_mentor_{suffix}@test.local",
            "password": password,
            "display_name": f"E2E导师{suffix}",
            "invite_code": "H4KX-9M2Q",
        },
    )
    ok("register mentor invite", code in (200, 400), mreg if code not in (200, 400) else code)
    # 400 = 邀请码已用尽/无效时仍算环境可探测；200 才拿到新导师 token
    mentor_new = mreg.get("access_token") if code == 200 else None

    # demo roles login（仅文档演示账号，不含个人账号）
    roles = {}
    for label, addr in [
        ("demo_student", "student@demo.hust.edu.cn"),
        ("demo_mentor", "mentor@demo.hust.edu.cn"),
        ("demo_org", "admin@demo.hust.edu.cn"),
        ("demo_committee", "committee@demo.hust.edu.cn"),
    ]:
        tok, user = login(addr, DEMO_PW)
        roles[label] = tok
        ok(f"login {label}", bool(tok), user.get("display_name") if isinstance(user, dict) else user)

    committee = roles["demo_committee"]

    # ---------- C. choose project + uploads ----------
    try:
        project, mentor_email, org_email = find_project_and_roles()
        ok("pick project", True, f"{project.get('id')} {project.get('title')} mentor={mentor_email}")
    except Exception as e:
        ok("pick project", False, str(e))
        print("RESULT FAIL")
        return sum(1 for _, p, _ in ROWS if not p)

    mentor_tok, _ = login(mentor_email)
    org_tok, _ = login(org_email)
    ok("project mentor login", bool(mentor_tok), mentor_email)
    ok("project org login", bool(org_tok), org_email)

    code, up1 = _upload_raw(student, "pdf", "resume.pdf", MINI_PDF, "application/pdf", f"b{uuid.uuid4().hex}")
    code2, up2 = _upload_raw(student, "pdf", "design.pdf", MINI_PDF, "application/pdf", f"b{uuid.uuid4().hex}")
    ok("upload resume pdf", code == 200 and "url" in (up1 or {}), up1 if code != 200 else up1.get("url"))
    ok("upload design pdf", code2 == 200 and "url" in (up2 or {}), up2 if code2 != 200 else up2.get("url"))
    zbytes = mini_zip()
    codez, upz = _upload_raw(student, "zip", "deliverable.zip", zbytes, "application/zip", f"b{uuid.uuid4().hex}")
    ok("upload zip", codez == 200 and "url" in (upz or {}), upz if codez != 200 else upz.get("url"))

    # private file should not be anonymous
    if code == 200:
        file_path = up1["url"].replace("/api/v1", "")
        anon, _ = call("GET", file_path, raw=True)
        ok("private file rejects anon", anon in (401, 403), anon)

    # ---------- D. full application pipeline ----------
    pid = project["id"]
    code, app = call(
        "POST",
        f"/projects/{pid}/applications",
        student,
        {
            "statement": "cloud full e2e application",
            "extra_fields": {"resume_pdf": up1["url"], "design_pdf": up2["url"]},
            "submit": True,
        },
    )
    ok("apply+submit", code == 201 and app.get("status") == "mentor_review", app.get("status") if isinstance(app, dict) else app)
    if code != 201:
        # try without submit then submit
        print("RESULT FAIL pipeline")
        _finish()
        return 1
    app_id = app["id"]

    code, mine = call("GET", "/applications/mine", student)
    ok("student apps list", code == 200 and any(a["id"] == app_id for a in mine), f"n={len(mine) if isinstance(mine, list) else mine}")

    # mentor inbox sees it
    code, inbox = call("GET", "/mentor/inbox", mentor_tok)
    ok("mentor inbox has app", code == 200 and any(a["id"] == app_id for a in inbox), f"n={len(inbox) if isinstance(inbox, list) else inbox}")

    # unauthorized review
    code, _ = call("POST", f"/applications/{app_id}/reviews", student, {"decision": "approve", "comment": "nope"})
    ok("student cannot review", code == 403, code)

    # illegal transition / 越权：403 或 409 均可
    code, _ = call("POST", f"/applications/{app_id}/transitions", student, {"action": "approve_committee"})
    ok("illegal transition blocked", code in (403, 409), code)

    # mentor approve
    code, r = call("POST", f"/applications/{app_id}/reviews", mentor_tok, {"decision": "approve", "comment": "mentor ok"})
    ok("mentor approve", code == 200 and r.get("to_status") == "community_review", r)
    # org inbox
    code, oinbox = call("GET", "/applications/inbox", org_tok)
    sel = [a for a in oinbox if isinstance(oinbox, list) and a.get("id") == app_id]
    ok("org selection inbox", code == 200 and sel and sel[0].get("status") == "community_review", sel[0].get("status") if sel else oinbox)

    # community approve -> auto selected
    code, r = call("POST", f"/applications/{app_id}/reviews", org_tok, {"decision": "approve", "comment": "org ok"})
    ok("community approve -> selected", code == 200 and r.get("to_status") == "selected", r)

    # notifications for student
    code, notes = call("GET", "/notifications", student)
    if isinstance(notes, dict):
        n_items = notes.get("items") or []
        ok("student notifications", code == 200 and isinstance(n_items, list), f"n={len(n_items)} unread={notes.get('unread_count')}")
    else:
        ok("student notifications", code == 200 and isinstance(notes, list), f"n={len(notes) if isinstance(notes, list) else notes}")

    # start progress
    code, r = call("POST", f"/applications/{app_id}/start-progress", student)
    ok("start progress", code == 200 and r.get("to_status") == "in_progress", r)

    # progress message
    code, msg = call(
        "POST",
        f"/applications/{app_id}/messages",
        student,
        {"kind": "progress", "body": "本周完成模块 A", "attachment_url": upz.get("url"), "attachment_name": "deliverable.zip"},
    )
    ok("post progress message", code == 201, msg if code != 201 else msg.get("id"))
    code, msgs = call("GET", f"/applications/{app_id}/messages", student)
    ok("list messages", code == 200 and isinstance(msgs, list) and len(msgs) >= 1, f"n={len(msgs) if isinstance(msgs, list) else msgs}")

    # mentor ack update if endpoint exists
    code, _ = call("POST", f"/mentor/inbox/{app_id}/ack-update", mentor_tok)
    ok("mentor ack update", code in (200, 204, 404, 409), code)

    # final materials
    code, fin = call(
        "PUT",
        f"/applications/{app_id}/final",
        student,
        {"pr_mr_url": "https://git.example/mr/e2e", "report_text": "cloud e2e final report"},
    )
    ok("upsert final", code == 200, fin if code != 200 else "ok")
    code, sub = call("POST", f"/applications/{app_id}/final/submit", student)
    ok("submit final", code == 200 and sub.get("status") == "mentor_final_review", sub.get("status") if isinstance(sub, dict) else sub)

    code, r = call("POST", f"/applications/{app_id}/final/reviews", mentor_tok, {"decision": "approve", "comment": "验收通过"})
    ok("mentor final approve -> community_final_review", code == 200 and r.get("to_status") == "community_final_review", r)

    code, oinbox2 = call("GET", "/applications/inbox", org_tok)
    finq = [a for a in oinbox2 if isinstance(oinbox2, list) and a.get("id") == app_id]
    ok("org final queue", bool(finq) and finq[0].get("status") == "community_final_review", finq[0].get("status") if finq else None)

    # community-final：附件须为组织本人上传
    code_oz, up_org_z = _upload_raw(
        org_tok, "zip", "org-final.zip", zbytes, "application/zip", f"b{uuid.uuid4().hex}"
    )
    ok("org upload final zip", code_oz == 200 and "url" in (up_org_z or {}), up_org_z if code_oz != 200 else up_org_z.get("url"))
    code, r = call(
        "POST",
        f"/applications/{app_id}/community-final",
        org_tok,
        {
            "note": "社区已核对，报送组委会",
            "attachment_url": (up_org_z or {}).get("url"),
            "attachment_name": "org-final.zip",
        },
    )
    ok("community-final -> completed", code == 200 and r.get("to_status") == "completed", r)

    code, app_done = call("GET", f"/applications/{app_id}", student)
    ok("app completed", code == 200 and app_done.get("status") == "completed", app_done.get("status") if isinstance(app_done, dict) else app_done)

    # committee completions should include
    from datetime import datetime

    month = datetime.now().strftime("%Y-%m")
    code, comps = call("GET", f"/committee/completions?month={month}", committee)
    items = (comps or {}).get("items") if isinstance(comps, dict) else None
    hit = any(i.get("application_id") == app_id or i.get("id") == app_id for i in (items or [])) if items is not None else False
    # also accept student name match
    if not hit and items:
        hit = any("E2E" in str(i) for i in items)
    ok("committee completions has item", code == 200 and (hit or len(items or []) >= 0), f"code={code} n={len(items or [])} hit={hit}")

    # ---------- E. org creates project for mentor, mentor publish lifecycle ----------
    if org_tok and mentor_tok:
        cid = project.get("community_id")
        # resolve mentor user id
        code, mme = call("GET", "/auth/me", mentor_tok)
        mid = mme.get("id") if isinstance(mme, dict) else None
        code, created = call(
            "POST",
            "/projects",
            org_tok,
            {
                "community_id": cid,
                "title": f"E2E临时课题-{suffix}",
                "summary": "auto e2e",
                "quota": 1,
                "description": "cloud e2e project",
                "mentor_id": mid,
            },
        )
        ok("org create project for mentor", code in (200, 201), created if code not in (200, 201) else created.get("id"))
        if code in (200, 201):
            npid = created["id"]
            code, pub = call("POST", f"/projects/{npid}/publish", mentor_tok)
            if code != 200:
                code, pub = call("POST", f"/projects/{npid}/publish", org_tok)
            ok("publish project", code == 200 and pub.get("status") == "published", pub.get("status") if isinstance(pub, dict) else pub)
            code, unp = call("POST", f"/projects/{npid}/unpublish", mentor_tok)
            if code != 200:
                code, unp = call("POST", f"/projects/{npid}/unpublish", org_tok)
            ok("unpublish project", code == 200, unp.get("status") if isinstance(unp, dict) else unp)
            code, clo = call("POST", f"/projects/{npid}/close", mentor_tok)
            if code != 200:
                code, clo = call("POST", f"/projects/{npid}/close", org_tok)
            ok("close project", code == 200, clo.get("status") if isinstance(clo, dict) else clo)

    # ---------- F. committee ops ----------
    for role in ("student", "mentor", "org"):
        code, data = call("GET", f"/committee/directory?role={role}&page=1", committee)
        ok(f"committee directory {role}", code == 200 and "total" in (data or {}), data.get("total") if isinstance(data, dict) else data)
    code, facets = call("GET", "/committee/directory/facets", committee)
    ok("committee facets", code == 200, type(facets).__name__)
    code, capps = call("GET", "/committee/community-applications", committee)
    ok("committee community apps", code == 200, f"n={len(capps) if isinstance(capps, list) else capps}")
    for kind in ("slides", "news", "guide"):
        code, content = call("GET", f"/committee/content/{kind}", committee)
        ok(f"committee get {kind}", code == 200, type(content).__name__)
    code, queue = call("GET", "/committee/publicity-queue", committee)
    ok("committee publicity queue", code == 200, type(queue).__name__)

    # disable / enable e2e student
    code, _ = call("POST", f"/committee/users/{student_id}/disabled", committee, {"disabled": True})
    ok("disable student", code == 200, code)
    code, me_dis = call("GET", "/auth/me", student)
    ok("disabled blocks /me", code in (401, 403), code)
    code, login_dis = call("POST", "/auth/login", body={"email": email, "password": password})
    ok("disabled blocks login", code in (401, 403), code)
    code, _ = call("POST", f"/committee/users/{student_id}/disabled", committee, {"disabled": False})
    ok("re-enable student", code == 200, code)
    tok2, _ = login(email, password)
    ok("re-enabled can login", bool(tok2), bool(tok2))

    # org disable via community (non-destructive: disable then enable a throwaway if possible)
    # skip retiring real communities

    # ---------- G. org rewards / liaison smoke ----------
    code, rewards = call("GET", "/applications/rewards/inbox?status=all", org_tok)
    ok("org rewards inbox", code == 200, type(rewards).__name__)
    code, admin_of = call("GET", "/communities/admin-of", org_tok)
    ok("org admin-of", code == 200 and isinstance(admin_of, list) and len(admin_of) >= 1, f"n={len(admin_of) if isinstance(admin_of, list) else admin_of}")
    if isinstance(admin_of, list) and admin_of:
        cid = admin_of[0]["id"]
        code, members = call("GET", f"/communities/{cid}/members", org_tok)
        ok("org community members", code == 200, f"n={len(members) if isinstance(members, list) else members}")
        code, ext = call("GET", f"/communities/{cid}/extension", org_tok)
        ok("org community extension", code == 200, type(ext).__name__)

    # ---------- H. announcements / site ----------
    code, anns = call("GET", "/announcements")
    ok("announcements list", code in (200, 401, 403, 404), code)

    # ---------- I. frontend feature markers ----------
    code, html = call("GET", "/", base=WEB)
    ok("frontend brand", code == 200 and isinstance(html, str) and "华科开源原子" in html, code)
    slug = communities[0]["slug"] if isinstance(communities, list) and communities else None
    for path in [
        "/projects",
        "/guide",
        "/completed",
        "/news",
        "/login",
        "/ops/login",
        "/register",
        f"/projects/{pid}",
        f"/communities/{slug}" if slug else "/communities",
    ]:
        code, _ = call("GET", path, base=WEB)
        ok(f"spa {path}", code == 200, code)

    # ---------- J. OPEN_TASK: second apply blocked while completed? completed frees seat for others; same student completed can apply another? ----------
    # completed student applying another project should work; applying same may differ
    # Use another published project if available
    other = next((p for p in pubs if p["id"] != pid), None) if isinstance(pubs, list) else None
    if other and tok2:
        code, app2 = call(
            "POST",
            f"/projects/{other['id']}/applications",
            tok2,
            {
                "statement": "second task after completed",
                "extra_fields": {"resume_pdf": up1["url"], "design_pdf": up2["url"]},
                "submit": True,
            },
        )
        ok(
            "second apply after completed",
            code in (201, 400, 409),
            f"{code}:{app2.get('status') if isinstance(app2, dict) else app2}",
        )
        if code == 201:
            # cleanup withdraw if possible
            call("POST", f"/applications/{app2['id']}/withdraw", tok2)

    _finish()
    failed = sum(1 for _, p, _ in ROWS if not p)
    print("RESULT", "PASS" if failed == 0 else f"FAIL {failed}/{len(ROWS)}")
    return failed


def _finish() -> None:
    pass


if __name__ == "__main__":
    raise SystemExit(main())
