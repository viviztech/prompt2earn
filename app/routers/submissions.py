from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.prompt import Prompt
from app.models.submission import Submission
from app.models.subscription import UserSubscription
from app.services.s3_service import create_presigned_post

router = APIRouter(tags=["submissions"])
templates = Jinja2Templates(directory="app/templates")


def get_user_active_sub(user_id, db: Session):
    return db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status == "active",
        UserSubscription.expires_at > datetime.utcnow(),
    ).first()


@router.post("/api/upload/presign")
async def presign_upload(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = await request.json()
    prompt_id = body.get("prompt_id")
    filename = body.get("filename", "")
    content_type = body.get("content_type", "")

    sub = get_user_active_sub(current_user.id, db)
    if not sub:
        raise HTTPException(status_code=403, detail="Active subscription required")

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.is_active == True).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if datetime.utcnow() > prompt.deadline:
        raise HTTPException(status_code=400, detail="Prompt deadline has passed")

    plan_name = sub.plan.name
    if prompt.visible_to and plan_name not in prompt.visible_to:
        raise HTTPException(status_code=403, detail="Your plan does not have access to this prompt")

    # Check duplicate submission
    existing = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.prompt_id == prompt_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already submitted for this prompt")

    category_name = prompt.category.name
    try:
        presign_data = create_presigned_post(
            category_name=category_name,
            user_id=str(current_user.id),
            prompt_id=str(prompt_id),
            filename=filename,
            content_type=content_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse(presign_data)


@router.get("/prompts/{prompt_id}", response_class=HTMLResponse)
async def prompt_detail(
    request: Request,
    prompt_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = get_user_active_sub(current_user.id, db)
    if not sub:
        return RedirectResponse(url="/subscriptions/plans", status_code=302)

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.is_active == True).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    plan_name = sub.plan.name
    if prompt.visible_to and plan_name not in prompt.visible_to:
        raise HTTPException(status_code=403, detail="Your plan does not have access to this prompt")

    existing_submission = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.prompt_id == prompt_id,
    ).first()

    is_past_deadline = datetime.utcnow() > prompt.deadline

    return templates.TemplateResponse("user/prompt_detail.html", {
        "request": request,
        "user": current_user,
        "prompt": prompt,
        "existing_submission": existing_submission,
        "is_past_deadline": is_past_deadline,
    })


@router.post("/prompts/{prompt_id}/submit")
async def submit_prompt(
    request: Request,
    prompt_id: str,
    s3_key: str = Form(...),
    original_filename: str = Form(...),
    file_type: str = Form(...),
    file_size: int = Form(0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = get_user_active_sub(current_user.id, db)
    if not sub:
        raise HTTPException(status_code=403, detail="Active subscription required")

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.is_active == True).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if datetime.utcnow() > prompt.deadline:
        raise HTTPException(status_code=400, detail="Deadline passed")

    existing = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.prompt_id == prompt_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already submitted")

    submission = Submission(
        user_id=current_user.id,
        prompt_id=prompt_id,
        file_url=s3_key,
        file_type=file_type,
        file_size_bytes=file_size,
        original_filename=original_filename,
        status="pending",
    )
    db.add(submission)
    db.commit()

    return RedirectResponse(url=f"/prompts/{prompt_id}?submitted=1", status_code=302)
