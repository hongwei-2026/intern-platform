"""API 路由聚合。"""

from fastapi import APIRouter

from intern_platform.api.routes import (
    announcements,
    applications,
    auth,
    communities,
    finals,
    health,
    inbox,
    integrations,
    messages,
    notifications,
    oauth,
    projects,
    reviews,
    uploads,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(communities.router)
api_router.include_router(projects.router)
api_router.include_router(inbox.router)
api_router.include_router(applications.router)
api_router.include_router(reviews.router)
api_router.include_router(announcements.router)
api_router.include_router(finals.router)
api_router.include_router(messages.router)
api_router.include_router(notifications.router)
api_router.include_router(uploads.router)
api_router.include_router(integrations.router)
