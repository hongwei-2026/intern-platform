"""门户外链：读 integration_settings。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.models.integration_setting import IntegrationSetting
from intern_platform.schemas.business import PortalLinksOut


class PortalService:
    KEY_MAP = {
        "portal.home_url": "home_url",
        "portal.docs_url": "docs_url",
        "portal.join_guide_url": "join_guide_url",
        "gitea.base_url": "gitea_url",
        "mirror.home_url": "mirror_url",
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def links(self) -> PortalLinksOut:
        rows = list(self.session.scalars(select(IntegrationSetting)).all())
        raw = {r.key: r.value for r in rows}
        data = {attr: raw.get(key) for key, attr in self.KEY_MAP.items()}
        return PortalLinksOut(**data, raw=raw)
