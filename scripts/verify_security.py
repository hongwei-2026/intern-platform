"""安全修复核对。项目根目录执行:

  python scripts/verify_security.py              # 本地 127.0.0.1:8001
  python scripts/verify_security.py --cloud       # 云端 intern.openatom.club
  set SECURITY_API_BASE=https://host/api/v1 && python scripts/verify_security.py
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import time
import urllib.error
import urllib.request
import uuid

LOCAL_BASE = "http://127.0.0.1:8001/api/v1"
CLOUD_BASE = "https://intern.openatom.club/api/v1"
BASE = LOCAL_BASE
PASS = 0
FAIL = 0
TIMEOUT = 8


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"[通过] {msg}")


def bad(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"[失败] {msg}")


def call(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(uuid.uuid4()),
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    ctx = ssl.create_default_context() if BASE.startswith("https://") else None
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def login(email: str) -> str | None:
    code, text = call("POST", "/auth/login", body={"email": email, "password": "Demo@123456"})
    if code != 200:
        return None
    return json.loads(text)["access_token"]


def main() -> int:
    global BASE, TIMEOUT
    parser = argparse.ArgumentParser(description="安全修复核对")
    parser.add_argument("--cloud", action="store_true", help="打云端 intern.openatom.club")
    parser.add_argument("--base", default="", help="自定义 API 前缀，如 https://host/api/v1")
    args = parser.parse_args()
    env_base = (os.environ.get("SECURITY_API_BASE") or "").strip()
    if args.base:
        BASE = args.base.rstrip("/")
    elif args.cloud:
        BASE = CLOUD_BASE
    elif env_base:
        BASE = env_base.rstrip("/")
    else:
        BASE = LOCAL_BASE
    TIMEOUT = 20 if BASE.startswith("https://") else 8
    label = "云端" if "openatom.club" in BASE or args.cloud else "本地"

    print()
    print(f"===== {label}安全修复核对 =====")
    print(f"地址: {BASE}")
    print()

    code, _ = call("GET", "/health")
    if code != 200:
        bad(f"后端不可用（HTTP {code}）。本地请先启动；云端请检查站点。")
        print()
        print("用法: python scripts/verify_security.py [--cloud]")
        return 1
    ok("后端已启动")

    # 优先纯学生；若演示学生被污染（挂了组织角色），再尝试其他演示学生
    student_email = "student@demo.hust.edu.cn"
    student = login(student_email)
    if student:
        code, text = call("GET", "/auth/me", token=student)
        me = json.loads(text) if code == 200 else {}
        roles = me.get("roles") or []
        polluted = any(
            r.get("code") in {"community_admin", "mentor", "committee"} for r in roles
        )
        if polluted:
            for alt in (
                "linxia@demo.hust.edu.cn",
                "zhouqi@demo.hust.edu.cn",
                "chenrui@demo.hust.edu.cn",
            ):
                alt_tok = login(alt)
                if not alt_tok:
                    continue
                c2, t2 = call("GET", "/auth/me", token=alt_tok)
                me2 = json.loads(t2) if c2 == 200 else {}
                roles2 = me2.get("roles") or []
                if not any(
                    r.get("code") in {"community_admin", "mentor", "committee"}
                    for r in roles2
                ):
                    student = alt_tok
                    student_email = alt
                    break
    admin = login("admin@demo.hust.edu.cn")
    if student:
        ok(f"学生账号能登录（{student_email}）")
    else:
        bad("学生账号登录失败")
        return 1
    if admin:
        ok("组织账号能登录")
    else:
        bad("组织账号登录失败")
        return 1

    code, text = call("GET", "/projects")
    projects = json.loads(text) if code == 200 else []
    proj = next((p for p in projects if "SpMV" in str(p.get("title", ""))), None)
    if proj is None and projects:
        proj = projects[0]

    code, text = call("GET", "/applications/mine", token=student)
    apps = json.loads(text) if code == 200 else []
    if not apps and proj:
        # 云端纯学生可能还没有申请：先建一条草稿再测自审拦截
        code, text = call(
            "POST",
            f"/projects/{proj['id']}/applications",
            token=student,
            body={
                "statement": "security-self-approve-check",
                "extra_fields": {},
                "submit": False,
            },
        )
        if code in (200, 201):
            apps = [json.loads(text)]
        else:
            # 可能已有申请记录但不在 mine 列表；继续用后续项目探测
            apps = []
    if not apps:
        bad("学生名下没有申请，测不了「不能自己审核」")
    else:
        app_id = apps[0]["id"]
        code, _ = call(
            "POST",
            f"/applications/{app_id}/transitions",
            token=student,
            body={"action": "approve_mentor"},
        )
        if code == 403:
            ok(f"学生不能自己把申请审过（申请 #{app_id}）")
        else:
            bad(f"学生自己审核没有被拦住（返回 {code}，应该是 403）")

    if proj:
        code, _ = call(
            "POST",
            f"/projects/{proj['id']}/applications",
            token=student,
            body={
                "statement": "verify",
                "extra_fields": {
                    "resume_pdf": "https://evil.example/uploads/files/x.pdf",
                    "design_pdf": "/api/v1/uploads/files/u1/ok.pdf",
                },
                "submit": False,
            },
        )
        if code == 400:
            ok("外网简历链接会被拒绝")
        else:
            bad(f"外网简历链接没有被拒绝（返回 {code}，应该是 400）")

    if apps:
        code, _ = call(
            "POST",
            f"/applications/{apps[0]['id']}/messages",
            token=student,
            body={
                "body": "progress",
                "kind": "progress",
                "attachment_url": "javascript:alert(1)",
                "attachment_name": "x.zip",
            },
        )
        if code == 400:
            ok("危险附件链接会被拒绝")
        else:
            bad(f"危险附件链接没有被拒绝（返回 {code}）")

    code, text = call("GET", "/communities/mine", token=admin)
    mine = json.loads(text) if code == 200 else []
    if not mine:
        bad("组织账号下没有社区")
    else:
        cid = mine[0]["id"]
        email = f"check_{int(time.time())}@demo.hust.edu.cn"
        c1, _ = call(
            "POST",
            f"/communities/{cid}/mentors",
            token=admin,
            body={"email": email, "password": "OldPass@123456", "display_name": "第一次"},
        )
        c2, _ = call(
            "POST",
            f"/communities/{cid}/mentors",
            token=admin,
            body={"email": email, "password": "NewPass@654321", "display_name": "想改密"},
        )
        old_ok, _ = call("POST", "/auth/login", body={"email": email, "password": "OldPass@123456"})
        new_ok, _ = call("POST", "/auth/login", body={"email": email, "password": "NewPass@654321"})
        if c1 == 201 and c2 == 201 and old_ok == 200 and new_ok == 401:
            ok("组织再次创建同一导师时，不会改掉对方密码")
        else:
            bad(f"创建导师改密防护异常（{c1}/{c2}, 旧密={old_ok}, 新密={new_ok}）")

    code, _ = call(
        "POST",
        "/auth/register-mentor",
        body={
            "email": f"poc_{int(time.time())}@demo.hust.edu.cn",
            "password": "Hunt@123456",
            "display_name": "poc",
            "invite_code": "MIRROR-DEMO",
        },
    )
    if code == 400:
        ok("旧的可猜邀请码 MIRROR-DEMO 已失效")
    else:
        bad(f"旧邀请码 MIRROR-DEMO 居然还能用（返回 {code}）")

    code, text = call("GET", "/auth/me", token=student)
    me = json.loads(text) if code == 200 else {}
    null_admin = [
        r
        for r in (me.get("roles") or [])
        if r.get("code") == "community_admin" and r.get("community_id") is None
    ]
    if not null_admin:
        ok("学生账号没有「空社区的全局管理员」权限")
    else:
        bad("学生账号仍带着空社区管理员角色")

    # 第二轮：上传必须落在本人目录
    if proj and student:
        me_code, me_text = call("GET", "/auth/me", token=student)
        me_body = json.loads(me_text) if me_code == 200 else {}
        uid = int(me_body.get("id") or 0)
        if uid:
            code, _ = call(
                "POST",
                f"/projects/{proj['id']}/applications",
                token=student,
                body={
                    "statement": "owner-check",
                    "extra_fields": {
                        "resume_pdf": f"/api/v1/uploads/files/u{uid + 999}/x.pdf",
                        "design_pdf": f"/api/v1/uploads/files/u{uid + 999}/y.pdf",
                    },
                    "submit": False,
                },
            )
            if code == 400:
                ok("不能挂别人上传目录里的附件")
            else:
                bad(f"挂别人上传目录没有被拒绝（返回 {code}）")

            # 图片/视频不再匿名公开
            code, _ = call("GET", f"/uploads/files/u{uid}/no-such-probe.png")
            if code in (401, 403, 404):
                ok("上传媒体文件不能匿名直接打开")
            else:
                bad(f"上传媒体仍可匿名访问（返回 {code}）")

    # 禁止 PATCH /me 手填平台 ID / 学号
    if student:
        before_code, before_text = call("GET", "/auth/me", token=student)
        before = json.loads(before_text) if before_code == 200 else {}
        forge_login = f"forged_{int(time.time())}"
        code, text = call(
            "PATCH",
            "/auth/me",
            token=student,
            body={
                "github_id": forge_login,
                "gitee_id": forge_login,
                "member_no": "FORGED-NO",
            },
        )
        after = json.loads(text) if code == 200 else {}
        forged = (
            after.get("github_id") == forge_login
            or after.get("gitee_id") == forge_login
            or after.get("member_no") == "FORGED-NO"
        )
        if code == 200 and not forged:
            ok("不能通过改资料手填 GitHub/Gitee/学号")
        elif code in (400, 422) and not forged:
            ok("不能通过改资料手填 GitHub/Gitee/学号")
        else:
            bad(f"手填平台 ID 未被拒绝（返回 {code}，github={after.get('github_id')!r}）")
        # 确认库内未变（用再次 GET）
        _, again_text = call("GET", "/auth/me", token=student)
        again = json.loads(again_text) if again_text else {}
        if again.get("github_id") == before.get("github_id") and again.get("member_no") == before.get(
            "member_no"
        ):
            pass  # already covered by ok/bad above
        elif forged:
            pass

    print()
    print(f"===== 结果：{PASS} 项通过，{FAIL} 项失败 =====")
    if FAIL == 0:
        print(f"这几条安全修复在{label}是生效的。")
    else:
        print("有失败项：把上面「失败」那几行发我。")
    print()
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
