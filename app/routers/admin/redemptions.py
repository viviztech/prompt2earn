from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.redemption import RedemptionRequest
from app.services.points_service import restore_points

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/redemptions", response_class=HTMLResponse)
async def list_redemptions(
    request: Request,
    status: str = "pending",
    page: int = 1,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    page_size = 20
    offset = (page - 1) * page_size
    query = db.query(RedemptionRequest)
    if status in ["pending", "processing", "completed", "rejected"]:
        query = query.filter(RedemptionRequest.status == status)
    redemptions = query.order_by(RedemptionRequest.created_at.asc()).offset(offset).limit(page_size).all()
    total = query.count()
    return templates.TemplateResponse("admin/redemptions.html", {
        "request": request,
        "user": current_user,
        "redemptions": redemptions,
        "status_filter": status,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size,
    })


@router.post("/redemptions/{redemption_id}/approve")
async def approve_redemption(
    request: Request,
    redemption_id: str,
    admin_note: str = Form(default=""),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    redemption = db.query(RedemptionRequest).filter(RedemptionRequest.id == redemption_id).first()
    if not redemption:
        raise HTTPException(status_code=404, detail="Redemption not found")
    redemption.status = "completed"
    redemption.admin_note = admin_note
    redemption.processed_by = current_user.id
    redemption.processed_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/admin/redemptions?status=pending", status_code=302)


@router.post("/redemptions/{redemption_id}/reject")
async def reject_redemption(
    request: Request,
    redemption_id: str,
    admin_note: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    redemption = db.query(RedemptionRequest).filter(RedemptionRequest.id == redemption_id).first()
    if not redemption:
        raise HTTPException(status_code=404, detail="Redemption not found")
    if redemption.status in ["completed", "rejected"]:
        raise HTTPException(status_code=400, detail="Already processed")

    redemption.status = "rejected"
    redemption.admin_note = admin_note
    redemption.processed_by = current_user.id
    redemption.processed_at = datetime.utcnow()
    db.flush()

    restore_points(
        redemption.user_id,
        redemption.id,
        redemption.points_requested,
        f"Redemption rejected: {admin_note}",
        db,
    )
    return RedirectResponse(url="/admin/redemptions?status=pending", status_code=302)
