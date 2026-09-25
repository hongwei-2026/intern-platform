"""健康检查 Schema。"""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    ok: bool
    db_driver: str
    app: str
    version: str
