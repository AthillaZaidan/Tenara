from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    # PRD API convention: {"data": ..., "error": null}
    return {"data": {"status": "ok"}, "error": None}
