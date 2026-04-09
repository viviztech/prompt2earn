from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.services.settings_service import get_all_settings, set_setting, seed_default_settings

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    seed_default_settings(db)
    all_settings = get_all_settings(db)

    # Group settings for the template
    groups = {}
    for key, meta in all_settings.items():
        g = meta["group"]
        groups.setdefault(g, []).append({"key": key, **meta})

    group_order = ["economics", "bonuses", "payments"]
    group_labels = {
        "economics": "💰 Points Economics & Redemption",
        "bonuses": "🎯 Bonus Configuration",
        "payments": "🏦 Manual Payment Details",
    }

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "user": current_user,
        "groups": groups,
        "group_order": group_order,
        "group_labels": group_labels,
        "saved": request.query_params.get("saved"),
    })


@router.post("/settings")
async def save_settings(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    form = await request.form()
    for key, value in form.items():
        if key.startswith("_"):
            continue
        set_setting(key, str(value).strip(), db)
    return RedirectResponse(url="/admin/settings?saved=1", status_code=302)
