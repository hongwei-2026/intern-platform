"""申请相关 Schema。"""

from pydantic import BaseModel, ConfigDict, Field


class TransitionRequest(BaseModel):
    action: str = Field(..., description="状态机动作，如 submit / approve_mentor")
    comment: str | None = None
    request_id: str | None = None
    actor_role: str | None = Field(
        default=None,
        description="已废弃：角色以服务端鉴权结果为准，客户端传入将被忽略",
    )
    idempotency_key: str | None = Field(
        default=None, description="幂等键，也可由 X-Idempotency-Key 传入"
    )
    trace_id: str | None = Field(
        default=None, description="链路追踪 ID，也可由 X-Trace-ID 传入"
    )
    version: int | None = Field(default=None, description="乐观锁版本号")


class TransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
    from_status: str
    to_status: str
    action: str
    idempotent_replay: bool = False
    version: int = 0
