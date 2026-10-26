"""Create a demo account per role in the configured database.

Development helper only.  It is purely additive: existing rows are left
exactly as they are, nothing is dropped, deleted or overwritten.

    python seed_dev_data.py                # uses DEV_SEED_PASSWORD or a default
    DEV_SEED_PASSWORD=mypass python seed_dev_data.py
"""

import os
import sys

from app.core.security import hash_password
from app.dependencies.database import SessionLocal, engine
from app.models import Base, Role, User

SEED_PASSWORD = os.getenv("DEV_SEED_PASSWORD", "digipass@123")

DEMO_USERS = [
    dict(
        id="A1234CS1001",
        first_name="Asha",
        last_name="Verma",
        role=Role.student,
        contact_details="9998887770",
        parent_email="parent@example.com",
        parents_phone="9876543210",
    ),
    dict(
        id="W0001",
        first_name="Wasim",
        last_name="Warden",
        role=Role.warden,
        contact_details="9998887771",
    ),
    dict(
        id="G0001",
        first_name="Gita",
        last_name="Guard",
        role=Role.guard,
        contact_details="9998887772",
    ),
    dict(
        id="AD001",
        first_name="Ada",
        last_name="Admin",
        role=Role.admin,
        contact_details="9998887773",
    ),
]


def main() -> int:
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    created, skipped = [], []
    try:
        for payload in DEMO_USERS:
            if session.get(User, payload["id"]) is not None:
                skipped.append(payload["id"])
                continue
            session.add(
                User(password=hash_password(SEED_PASSWORD), is_active=True, **payload)
            )
            created.append(payload["id"])
        session.commit()
    finally:
        session.close()

    print(f"Database: {engine.url}")
    if created:
        print(f"Created : {', '.join(created)}  (password: {SEED_PASSWORD})")
    if skipped:
        print(f"Existing: {', '.join(skipped)}  (left untouched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
