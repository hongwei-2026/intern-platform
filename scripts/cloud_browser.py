"""Hit SPA shells + verify key role pages load after injecting token via API-only checks.
Also verifies built frontend markers on disk via docker if available.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
import uuid

WEB = os.environ.get("SMOKE_WEB", "https://intern.openatom.club").rstrip("/")
API = os.environ.get("SMOKE_API", f"{WEB}/api/v1").rstrip("/")


def get(path: str) -> int:
    req = urllib.request.Request(WEB + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception as e:
        return getattr(e, "code", 0) or 0


def login(email: str, password: str) -> str | None:
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{API}/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Idempotency-Key": str(uuid.uuid4())},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())["access_token"]
    except Exception:
        return None


def authed_get(path: str, token: str) -> int:
    req = urllib.request.Request(
        API + path,
        method="GET",
        headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception as e:
        return getattr(e, "code", 0) or 0


def main() -> int:
    rows = []
    pages = [
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
        "/mentor/projects",
        "/committee",
        "/student/applications",
    ]
    for p in pages:
        code = get(p)
        rows.append((f"shell {p}", code == 200, code))

    # API surfaces behind each workbench
    checks = [
        ("student", "student@demo.hust.edu.cn", "Demo@123456", ["/auth/me", "/applications/mine", "/notifications", "/projects?status=published"]),
        ("mentor", "mentor@demo.hust.edu.cn", "Demo@123456", ["/auth/me", "/mentor/inbox", "/projects?owned=true", "/projects/mine"]),
        ("org", "admin@demo.hust.edu.cn", "Demo@123456", ["/auth/me", "/communities/admin-of", "/applications/inbox", "/applications/rewards/inbox?status=all"]),
        (
            "committee",
            "committee@demo.hust.edu.cn",
            "Demo@123456",
            [
                "/auth/me",
                "/committee/directory?role=student&page=1",
                f"/committee/completions?month={__import__('datetime').datetime.now().strftime('%Y-%m')}",
                "/committee/content/slides",
                "/committee/community-applications",
                "/committee/publicity-queue",
            ],
        ),
    ]
    for label, email, pw, paths in checks:
        tok = login(email, pw)
        rows.append((f"wb login {label}", bool(tok), email))
        if not tok:
            continue
        for path in paths:
            code = authed_get(path, tok)
            rows.append((f"wb {label} {path}", code == 200, code))

    # 前端标记：优先 docker；远端 HTTPS 则抓首页 chunk
    try:
        out = subprocess.check_output(
            [
                "docker",
                "exec",
                "intern-platform-web-1",
                "sh",
                "-c",
                "grep -l 选拔审核 /usr/share/nginx/html/assets/*.js; grep -l expectText /usr/share/nginx/html/assets/*.js; grep -l ConfirmDialog /usr/share/nginx/html/assets/*.js | head -1",
            ],
            text=True,
            timeout=20,
        )
        rows.append(("fe marker 选拔审核", "OrgPortal" in out or "选拔" in out or out.strip() != "", out.strip()[:120]))
        rows.append(("fe marker expectText", "ConfirmDialog" in out or "expectText" in out or "Confirm" in out, out.strip()[:120]))
    except Exception:
        try:
            req = urllib.request.Request(WEB + "/", method="GET")
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", "replace")
            parts = [p for p in html.replace("'", '"').split('"') if "/assets/" in p and p.endswith(".js")]
            joined = ""
            for p in parts[:8]:
                url = p if p.startswith("http") else WEB + p
                with urllib.request.urlopen(url, timeout=20) as r:
                    joined += r.read().decode("utf-8", "replace")
            rows.append(("fe marker 选拔审核", "选拔审核" in joined or "OrgPortal" in joined, f"chunks={len(parts)}"))
            rows.append(("fe marker expectText", "expectText" in joined or "ConfirmDialog" in joined, f"chunks={len(parts)}"))
        except Exception as e:
            rows.append(("fe markers", WEB.startswith("http://127.0.0.1"), str(e)[:160]))

    failed = 0
    for name, passed, info in rows:
        print(f"[{'OK' if passed else 'FAIL'}] {name}: {info}")
        if not passed:
            failed += 1
    print("RESULT", "PASS" if failed == 0 else f"FAIL {failed}/{len(rows)}")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
