from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.prompt import Prompt, PromptCategory

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/prompts", response_class=HTMLResponse)
async def list_prompts(
    request: Request,
    page: int = 1,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    page_size = 20
    offset = (page - 1) * page_size
    prompts = db.query(Prompt).order_by(Prompt.created_at.desc()).offset(offset).limit(page_size).all()
    total = db.query(Prompt).count()
    return templates.TemplateResponse("admin/prompts.html", {
        "active_nav": "prompts",
        "request": request,
        "user": current_user,
        "prompts": prompts,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size,
    })


@router.get("/prompts/new", response_class=HTMLResponse)
async def new_prompt_page(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    categories = db.query(PromptCategory).filter(PromptCategory.is_active == True).all()
    return templates.TemplateResponse("admin/prompt_form.html", {
        "active_nav": "prompts",
        "request": request,
        "user": current_user,
        "categories": categories,
        "prompt": None,
    })


@router.post("/prompts/new")
async def create_prompt(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category_id: str = Form(...),
    point_value: int = Form(...),
    deadline: str = Form(...),
    visible_to: list = Form(default=["basic", "pro", "premium"]),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    deadline_dt = datetime.fromisoformat(deadline)
    prompt = Prompt(
        title=title,
        description=description,
        category_id=category_id,
        point_value=point_value,
        deadline=deadline_dt,
        visible_to=visible_to,
        created_by=current_user.id,
        is_active=True,
    )
    db.add(prompt)
    db.commit()
    return RedirectResponse(url="/admin/prompts", status_code=302)


@router.get("/prompts/{prompt_id}/edit", response_class=HTMLResponse)
async def edit_prompt_page(
    request: Request,
    prompt_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    categories = db.query(PromptCategory).filter(PromptCategory.is_active == True).all()
    return templates.TemplateResponse("admin/prompt_form.html", {
        "active_nav": "prompts",
        "request": request,
        "user": current_user,
        "prompt": prompt,
        "categories": categories,
    })


@router.post("/prompts/{prompt_id}/edit")
async def update_prompt(
    request: Request,
    prompt_id: str,
    title: str = Form(...),
    description: str = Form(...),
    category_id: str = Form(...),
    point_value: int = Form(...),
    deadline: str = Form(...),
    visible_to: list = Form(default=["basic", "pro", "premium"]),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.title = title
    prompt.description = description
    prompt.category_id = category_id
    prompt.point_value = point_value
    prompt.deadline = datetime.fromisoformat(deadline)
    prompt.visible_to = visible_to
    db.commit()
    return RedirectResponse(url="/admin/prompts", status_code=302)


@router.post("/prompts/{prompt_id}/delete")
async def delete_prompt(
    request: Request,
    prompt_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if prompt:
        prompt.is_active = False
        db.commit()
    return RedirectResponse(url="/admin/prompts", status_code=302)
