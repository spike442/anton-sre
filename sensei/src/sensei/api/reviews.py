from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from sensei.domain.models import ReviewStatus

router = APIRouter(prefix="/reviews", tags=["reviews"])


def require_control_auth(request: Request, authorization: str | None) -> None:
    token = request.app.state.runtime.settings.control_token
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="invalid Sensei control authorization")


@router.get("")
def reviews(
    request: Request, limit: int = Query(default=50, ge=1, le=200), status: ReviewStatus | None = Query(default=None)
) -> dict:
    records = request.app.state.runtime.poller.reviews.list_reviews(limit=limit, status=status)
    return {"reviews": records}


@router.post("/check", status_code=202)
def check_existing_reviews(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    require_control_auth(request, authorization)
    poller = request.app.state.runtime.poller
    if poller.running:
        raise HTTPException(status_code=409, detail="Sensei check already running")
    background_tasks.add_task(poller.run_once)
    return {"status": "started"}


@router.delete("/{review_id}", status_code=204)
def delete_review(
    review_id: int,
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    require_control_auth(request, authorization)
    try:
        request.app.state.runtime.poller.reviews.delete(review_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail="review not found") from exc
