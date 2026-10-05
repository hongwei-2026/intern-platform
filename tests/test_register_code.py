"""学生注册：邮箱 + 密码，无需邮箱验证码。"""

from __future__ import annotations

import uuid


def test_register_with_email_password(client_and_db) -> None:
    client, _, _ = client_and_db
    email = f"reg_{uuid.uuid4().hex[:8]}@test.local"

    ok = client.post(
        "/api/v1/auth/register",
        headers={"X-Idempotency-Key": str(uuid.uuid4())},
        json={
            "email": email,
            "password": "Demo@123456",
            "display_name": "reg",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["user"]["email"] == email

    dup = client.post(
        "/api/v1/auth/register",
        headers={"X-Idempotency-Key": str(uuid.uuid4())},
        json={
            "email": email,
            "password": "Demo@123456",
            "display_name": "reg2",
        },
    )
    assert dup.status_code == 400
