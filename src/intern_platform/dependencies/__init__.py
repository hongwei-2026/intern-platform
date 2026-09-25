"""FastAPI 依赖包。"""

from intern_platform.dependencies.auth import (
    AuthUser,
    RoleBinding,
    create_access_token,
    get_current_user,
    get_optional_user,
    hash_password,
    require_roles,
    verify_password,
)
from intern_platform.dependencies.ledger import (
    LedgerRequestContext,
    get_ledger_context,
    require_idempotency_key,
)

__all__ = [
    "AuthUser",
    "LedgerRequestContext",
    "RoleBinding",
    "create_access_token",
    "get_current_user",
    "get_ledger_context",
    "get_optional_user",
    "hash_password",
    "require_idempotency_key",
    "require_roles",
    "verify_password",
]
