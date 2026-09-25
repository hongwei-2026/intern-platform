"""集成 / 门户外链。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.integration.portal import PortalService
from intern_platform.schemas.business import PortalLinksOut

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/links", response_model=PortalLinksOut)
def portal_links(db: Session = Depends(get_db)) -> PortalLinksOut:
    return PortalService(db).links()
