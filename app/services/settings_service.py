"""
Settings service — reads from platform_settings table (admin-editable),
falls back to config.py values if not yet seeded.
"""
from sqlalchemy.orm import Session
from app.models.settings import PlatformSettings

# Default values — used only if the DB row doesn't exist yet
DEFAULTS = {
    # Points economics
    "points_per_inr":              ("1",     "Points per ₹1 (conversion rate)", "economics"),
    "minimum_redemption_points":   ("500",   "Minimum points to redeem", "economics"),
    "points_expiry_days":          ("180",   "Days before earned points expire", "economics"),
    # Bonuses
    "welcome_bonus_points":        ("10",    "Points awarded on first submission approval", "bonuses"),
    "weekly_streak_bonus_points":  ("20",    "Points awarded every 7-day streak", "bonuses"),
    "monthly_streak_bonus_points": ("50",    "Points awarded for 25+ active days in a month", "bonuses"),
    "monthly_streak_threshold":    ("25",    "Active days needed for monthly streak bonus", "bonuses"),
    # Company economics
    "company_profit_pct":          ("20",    "Company profit percentage (rest goes to user pool)", "economics"),
    # Manual payment details
    "manual_upi_id":               ("",      "UPI ID shown to users for manual payment", "payments"),
    "manual_account_name":         ("",      "Bank account holder name", "payments"),
    "manual_bank_name":            ("",      "Bank name", "payments"),
    "manual_bank_account":         ("",      "Bank account number", "payments"),
    "manual_bank_ifsc":            ("",      "Bank IFSC code", "payments"),
}

LABELS = {k: v[1] for k, v in DEFAULTS.items()}
GROUPS = {k: v[2] for k, v in DEFAULTS.items()}
DESCRIPTIONS = {
    "points_per_inr":              "1 point = ₹1 means users earn ₹1 per approved point",
    "minimum_redemption_points":   "Users must accumulate at least this many points to request cash",
    "points_expiry_days":          "Points earned from tasks expire after this many days",
    "welcome_bonus_points":        "One-time bonus on first ever approved submission",
    "weekly_streak_bonus_points":  "Awarded automatically every 7 consecutive active days",
    "monthly_streak_bonus_points": "Awarded on the 1st of each month for high engagement",
    "monthly_streak_threshold":    "Number of days user must submit in a month to earn monthly bonus",
    "company_profit_pct":          "Percentage of each subscription retained as company profit (rest = user pool)",
    "manual_upi_id":               "Shown in Step 1 of manual payment page",
    "manual_account_name":         "Account holder name shown for bank transfer",
    "manual_bank_name":            "Bank name shown for bank transfer",
    "manual_bank_account":         "Account number shown for bank transfer",
    "manual_bank_ifsc":            "IFSC code shown for bank transfer",
}


def get_setting(key: str, db: Session) -> str:
    row = db.query(PlatformSettings).filter(PlatformSettings.key == key).first()
    if row:
        return row.value
    return DEFAULTS.get(key, ("",))[0]


def get_setting_int(key: str, db: Session) -> int:
    return int(get_setting(key, db) or 0)


def get_setting_float(key: str, db: Session) -> float:
    return float(get_setting(key, db) or 0)


def set_setting(key: str, value: str, db: Session):
    row = db.query(PlatformSettings).filter(PlatformSettings.key == key).first()
    if row:
        row.value = value
    else:
        row = PlatformSettings(
            key=key,
            value=value,
            label=LABELS.get(key, key),
            description=DESCRIPTIONS.get(key, ""),
            group=GROUPS.get(key, "general"),
        )
        db.add(row)
    db.commit()


def get_all_settings(db: Session) -> dict:
    """Return all settings as {key: value}, filling in defaults for missing keys."""
    rows = {r.key: r for r in db.query(PlatformSettings).all()}
    result = {}
    for key, (default, label, group) in DEFAULTS.items():
        result[key] = {
            "value": rows[key].value if key in rows else default,
            "label": label,
            "description": DESCRIPTIONS.get(key, ""),
            "group": group,
        }
    return result


def seed_default_settings(db: Session):
    """Insert default rows for any missing settings keys."""
    from app.config import get_settings
    config = get_settings()
    # Seed from config values where available
    config_map = {
        "points_per_inr": str(config.POINTS_PER_INR),
        "minimum_redemption_points": str(config.MINIMUM_REDEMPTION_POINTS),
        "points_expiry_days": str(config.POINTS_EXPIRY_DAYS),
        "manual_upi_id": config.MANUAL_UPI_ID or "",
        "manual_account_name": config.MANUAL_ACCOUNT_NAME or "",
        "manual_bank_name": config.MANUAL_BANK_NAME or "",
        "manual_bank_account": config.MANUAL_BANK_ACCOUNT or "",
        "manual_bank_ifsc": config.MANUAL_BANK_IFSC or "",
    }
    for key, (default, label, group) in DEFAULTS.items():
        exists = db.query(PlatformSettings).filter(PlatformSettings.key == key).first()
        if not exists:
            value = config_map.get(key, default)
            db.add(PlatformSettings(
                key=key,
                value=value,
                label=label,
                description=DESCRIPTIONS.get(key, ""),
                group=group,
            ))
    db.commit()
