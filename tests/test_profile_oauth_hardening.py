"""资料手填平台 ID 禁止 + OAuth 绑定唯一性 / 会话校验。"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from intern_platform.models.user import User
from intern_platform.services import oauth_service as oauth


def _idem() -> str:
    return str(uuid.uuid4())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str = "Demo@123456") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_patch_me_ignores_provider_ids_and_member_no(client_and_db) -> None:
    client, SessionLocal, _ = client_and_db
    token = _login(client, "student@test.local")

    r = client.patch(
        "/api/v1/auth/me",
        headers=_auth(token),
        json={
            "display_name": "学生改名",
            "github_id": "evil-hacker",
            "gitee_id": "forged",
            "member_no": "FORGED-001",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["display_name"] == "学生改名"
    assert body.get("github_id") in (None, "")
    assert body.get("gitee_id") in (None, "")
    assert body.get("member_no") in (None, "")

    db = SessionLocal()
    try:
        u = db.scalar(select(User).where(User.email == "student@test.local"))
        assert u is not None
        assert u.github_id is None
        assert u.gitee_id is None
        assert u.member_no is None
        assert u.display_name == "学生改名"
    finally:
        db.close()


def test_bind_login_rejects_duplicate_provider_account(client_and_db) -> None:
    _client, SessionLocal, _ = client_and_db
    db = SessionLocal()
    try:
        a = db.scalar(select(User).where(User.email == "student@test.local"))
        b = db.scalar(select(User).where(User.email == "outsider@test.local"))
        assert a is not None and b is not None
        a.github_id = "same-login"
        db.add(a)
        db.commit()
        try:
            oauth.bind_login(db, b, "github_id", "same-login", provider="github")
            raise AssertionError("expected ValueError for duplicate bind")
        except ValueError as exc:
            assert "已绑定" in str(exc)
    finally:
        db.close()


def test_oauth_state_consumed_once() -> None:
    state = oauth.create_oauth_state(user_id=1, provider="github")
    first = oauth.consume_oauth_state(state)
    assert first["sub"] == "1"
    assert first["provider"] == "github"
    try:
        oauth.consume_oauth_state(state)
        raise AssertionError("replay should fail")
    except ValueError as exc:
        assert "已使用" in str(exc)


def test_oauth_bind_cookie_must_match_state_user(client_and_db) -> None:
    client, SessionLocal, _ = client_and_db
    token = _login(client, "student@test.local")
    start = client.get("/api/v1/auth/oauth/github/start", headers=_auth(token))
    assert start.status_code == 200, start.text
    state = start.json()["state"]
    # 无 cookie：回调应失败并重定向到前端错误
    cb = client.get(
        "/api/v1/auth/oauth/github/callback",
        params={"code": "dummy", "state": state},
        follow_redirects=False,
    )
    assert cb.status_code == 302
    loc = cb.headers.get("location") or ""
    assert "bind_ok=0" in loc
    assert "绑定会话" in loc or "bind_err" in loc


def test_oauth_unbind_endpoint(client_and_db) -> None:
    client, SessionLocal, _ = client_and_db
    db = SessionLocal()
    try:
        u = db.scalar(select(User).where(User.email == "student@test.local"))
        assert u is not None
        u.github_id = "to-unbind"
        db.add(u)
        db.commit()
    finally:
        db.close()

    token = _login(client, "student@test.local")
    r = client.delete("/api/v1/auth/oauth/github/bind", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json().get("github_id") in (None, "")


def test_uploaded_image_requires_auth(client_and_db, tmp_path, monkeypatch) -> None:
    client, SessionLocal, _ = client_and_db
    from intern_platform.api.routes import uploads as uploads_mod

    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(uploads_mod, "UPLOAD_ROOT", root)

    token = _login(client, "student@test.local")
    db = SessionLocal()
    try:
        me = db.scalar(select(User).where(User.email == "student@test.local"))
        assert me is not None
        uid = me.id
    finally:
        db.close()

    user_dir = root / f"u{uid}"
    user_dir.mkdir(parents=True)
    (user_dir / "pic.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    )

    anon = client.get(f"/api/v1/uploads/files/u{uid}/pic.png")
    assert anon.status_code == 401, anon.text

    ok = client.get(
        f"/api/v1/uploads/files/u{uid}/pic.png",
        headers=_auth(token),
    )
    assert ok.status_code == 200, ok.text
