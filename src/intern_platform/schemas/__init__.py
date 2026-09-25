"""Pydantic schemas。"""

from intern_platform.schemas.application import TransitionRequest, TransitionResponse
from intern_platform.schemas.health import HealthResponse

__all__ = ["HealthResponse", "TransitionRequest", "TransitionResponse"]
