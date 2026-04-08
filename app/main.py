from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.background import BackgroundScheduler
import logging

from app.config import get_settings
from app.routers import auth, user, subscription, submissions, points, redemption
from app.routers.admin import dashboard as admin_dashboard
from app.routers.admin import prompts as admin_prompts
from app.routers.admin import submissions as admin_submissions
from app.routers.admin import users as admin_users
from app.routers.admin import plans as admin_plans
from app.routers.admin import redemptions as admin_redemptions
from app.routers.admin import reports as admin_reports

settings = get_settings()
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(subscription.router)
app.include_router(submissions.router)
app.include_router(points.router)
app.include_router(redemption.router)
app.include_router(admin_dashboard.router, prefix="/admin")
app.include_router(admin_prompts.router, prefix="/admin")
app.include_router(admin_submissions.router, prefix="/admin")
app.include_router(admin_users.router, prefix="/admin")
app.include_router(admin_plans.router, prefix="/admin")
app.include_router(admin_redemptions.router, prefix="/admin")
app.include_router(admin_reports.router, prefix="/admin")


@app.get("/")
async def root(request: Request):
    from app.dependencies import get_current_user_optional
    from app.database import get_db
    db = next(get_db())
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("landing.html", {"request": request})


# APScheduler for background jobs
scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    from app.tasks.expire_points import expire_points_job
    scheduler.add_job(expire_points_job, "cron", hour=2, minute=0)
    scheduler.start()
    logger.info("Scheduler started")


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()
