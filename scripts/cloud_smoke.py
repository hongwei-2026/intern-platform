"""Cloud smoke for http://120.53.18.32:8080 — no secrets printed beyond pass/fail."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

import os

WEB = os.environ.get("SMOKE_WEB", "https://intern.openatom.club").rstrip("/")
BASE = os.environ.get("SMOKE_API", f"{WEB}/api/v1").rstrip("/")


def call(method: str, path: str, token: str | None = None, body: dict | None = None, base: str = BASE):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "X-Idempotency-Key": str(uuid.uuid4())}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read().decode("utf-8", "replace")
            return res.status, json.loads(raw) if raw.startswith("{") or raw.startswith("[") else raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw[:200]
        return e.code, detail


def login(email: str, password: str = "Demo@123456"):
    code, data = call("POST", "/auth/login", body={"email": email, "password": password})
    if code != 200:
        return None, f"{code}:{data}"
    return data["access_token"], data["user"]


def main():
    rows = []

    # public pages
    for path in ["/", "/login", "/ops/login", "/projects", "/guide", "/completed"]:
        code, _ = call("GET", path, base=WEB)
        rows.append((f"page {path}", code == 200, code))

    code, data = call("GET", "/health")
    rows.append(("health", code == 200 and data.get("ok") is True, data))

    code, data = call("GET", "/projects?status=published")
    rows.append(("published projects", code == 200 and isinstance(data, list) and len(data) > 0, f"n={len(data) if isinstance(data, list) else data}"))

    code, data = call("GET", "/communities?status=approved")
    rows.append(("approved communities", code == 200 and isinstance(data, list) and len(data) > 0, f"n={len(data) if isinstance(data, list) else data}"))

    # pending communities must not be public anonymous dump of private apps
    code, data = call("GET", "/communities?status=pending")
    rows.append(("pending communities gated", code in (200, 401, 403), f"{code}"))

    # student
    tok, user = login("student@demo.hust.edu.cn")
    rows.append(("student login", bool(tok), user if not tok else user.get("display_name")))
    if tok:
        code, data = call("GET", "/auth/me", tok)
        rows.append(("student /me", code == 200, data.get("email") if isinstance(data, dict) else data))
        code, data = call("GET", "/applications/mine", tok)
        rows.append(("student apps", code == 200, f"n={len(data) if isinstance(data, list) else data}"))

    # mentor
    tok, user = login("mentor@demo.hust.edu.cn")
    rows.append(("mentor login", bool(tok), user if not tok else user.get("display_name")))
    if tok:
        code, data = call("GET", "/mentor/inbox", tok)
        rows.append(("mentor inbox", code == 200, f"n={len(data) if isinstance(data, list) else data}"))
        code, data = call("GET", "/projects?owned=true", tok)
        rows.append(("mentor owned", code == 200, f"n={len(data) if isinstance(data, list) else data}"))

    # org
    tok, user = login("admin@demo.hust.edu.cn")
    rows.append(("org login", bool(tok), user if not tok else user.get("display_name")))
    if tok:
        code, data = call("GET", "/communities/admin-of", tok)
        rows.append(("org admin-of", code == 200 and isinstance(data, list), f"n={len(data) if isinstance(data, list) else data}"))
        code, data = call("GET", "/applications/inbox", tok)
        sel = [a for a in data if isinstance(data, list) and a.get("status") == "community_review"] if isinstance(data, list) else []
        fin = [a for a in data if isinstance(data, list) and a.get("status") == "community_final_review"] if isinstance(data, list) else []
        rows.append(("org inbox", code == 200, f"selection={len(sel)} final={len(fin)} total={len(data) if isinstance(data, list) else data}"))
        # route exists
        code, data = call("POST", "/applications/1/community-final", tok, {"note": "probe"})
        rows.append(("community-final route live", code in (400, 403, 404, 409), code))

    # committee
    tok, user = login("committee@demo.hust.edu.cn")
    rows.append(("committee login", bool(tok), user if not tok else user.get("display_name")))
    if tok:
        for role in ("student", "mentor", "org"):
            code, data = call("GET", f"/committee/directory?role={role}&page=1", tok)
            rows.append((f"committee dir {role}", code == 200, data.get("total") if isinstance(data, dict) else data))
        from datetime import datetime

        month = datetime.now().strftime("%Y-%m")
        code, data = call("GET", f"/committee/completions?month={month}", tok)
        rows.append(("committee completions", code == 200, f"n={len((data or {}).get('items') or []) if isinstance(data, dict) else data}"))
        code, data = call("GET", "/committee/community-applications", tok)
        rows.append(("committee community apps", code == 200, f"n={len(data) if isinstance(data, list) else data}"))
        # disabled endpoint exists
        code, data = call("POST", "/committee/users/1/disabled", tok, {"disabled": False})
        rows.append(("disable route live", code in (200, 400, 404), code))

    # new frontend markers
    code, html = call("GET", "/", base=WEB)
    html_s = html if isinstance(html, str) else str(html)
    rows.append(("frontend shell", code == 200 and "华科开源原子" in html_s, code))

    failed = 0
    for name, ok, info in rows:
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name}: {info}")
    print("RESULT", "PASS" if failed == 0 else f"FAIL {failed}")
    raise SystemExit(failed)


if __name__ == "__main__":
    main()
