from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# -------------------------------------------------------------------
# Register feature routers below as you build them, e.g.:
#
from app.api.v1 import projects, evaluate, compare

router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(evaluate.router, prefix="/evaluate", tags=["Evaluate"])
router.include_router(compare.router, prefix="/compare", tags=["Compare"])
