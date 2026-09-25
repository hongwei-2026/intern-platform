"""领域服务导出。"""

from intern_platform.services.state_machine import (
    ApplicationStatus,
    IllegalTransitionError,
    TransitionAction,
    allowed_actions,
    resolve_transition,
)

# application_workflow / ledger 请按需直接从子模块导入，避免与 repositories 循环依赖。

__all__ = [
    "ApplicationStatus",
    "IllegalTransitionError",
    "TransitionAction",
    "allowed_actions",
    "resolve_transition",
]
