from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.submission import Submission
from app.services.points_service import award_points
from app.services.s3_service import create_presigned_get_url
from app.services.email_service import send_approval_email, send_rejection_email

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/submissions", response_class=HTMLResponse)
async def list_submissions(
    request: Request,
    status: str = "pending",
    page: int = 1,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    page_size = 20
    offset = (page - 1) * page_size
    query = db.query(Submission)
    if status in ["pending", "approved", "rejected"]:
        query = query.filter(Submission.status == status)
    submissions = query.order_by(Submission.submitted_at.asc()).offset(offset).limit(page_size).all()
    total = query.count()
    return templates.TemplateResponse("admin/submissions.html", {
        "active_nav": "submissions",
        "request": request,
        "user": current_user,
        "submissions": submissions,
        "status_filter": status,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size,
    })


@router.get("/submissions/{submission_id}", response_class=HTMLResponse)
async def view_submission(
    request: Request,
    submission_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    preview_url = create_presigned_get_url(submission.file_url, expiry_seconds=900)
    return templates.TemplateResponse("admin/submission_review.html", {
        "active_nav": "submissions",
        "request": request,
        "user": current_user,
        "submission": submission,
        "preview_url": preview_url,
    })


@router.post("/submissions/{submission_id}/approve")
async def approve_submission(
    request: Request,
    submission_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != "pending":
        raise HTTPException(status_code=400, detail="Submission already reviewed")

    submission.reviewed_by = current_user.id
    submission.reviewed_at = datetime.utcnow()
    db.flush()

    points = award_points(submission_id, db)

    send_approval_email(
        submission.user.email,
        submission.user.full_name,
        submission.prompt.title,
        points,
    )
    return RedirectResponse(url="/admin/submissions?status=pending", status_code=302)


@router.post("/submissions/{submission_id}/reject")
async def reject_submission(
    request: Request,
    submission_id: str,
    review_note: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != "pending":
        raise HTTPException(status_code=400, detail="Submission already reviewed")

    submission.status = "rejected"
    submission.review_note = review_note
    submission.reviewed_by = current_user.id
    submission.reviewed_at = datetime.utcnow()
    db.commit()

    send_rejection_email(
        submission.user.email,
        submission.user.full_name,
        submission.prompt.title,
        review_note,
    )
    return RedirectResponse(url="/admin/submissions?status=pending", status_code=302)
