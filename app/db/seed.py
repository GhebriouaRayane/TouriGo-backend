from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import User, UserRole

DEMO_USER_EMAILS = {
    "admin@3ich.app",
    "karim@3ich.app",
    "samira@3ich.app",
    "amina@3ich.app",
    "yacine@3ich.app",
}

REAL_ADMIN_EMAIL = "rayaneghebrioua10@gmail.com"


def seed_database(db: Session) -> None:
    demo_users = db.query(User).filter(User.email.in_(sorted(DEMO_USER_EMAILS))).all()
    for demo_user in demo_users:
        db.delete(demo_user)

    real_admin = db.query(User).filter(User.email == REAL_ADMIN_EMAIL).first()
    if real_admin:
        real_admin.role = UserRole.ADMIN.value
        real_admin.is_active = True
        db.add(real_admin)

    db.flush()
