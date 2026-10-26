"""Verify that the configured database matches what the application expects.

Run this once after pointing ``DATABASE_URL`` at a real database - it answers
"will the FastAPI backend work against this instance, and is the existing data
intact?" without touching a single row.

    python check_database.py
    python check_database.py --url "postgresql+psycopg2://user:pass@host:5432/db"

It is strictly READ-ONLY: it opens a connection, reads the system catalogs,
counts rows and loads one object through the ORM. It never creates, alters,
drops or writes anything.

Exit code 0 = ready to use, 1 = something needs attention.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models import Base, LeavePass, Log, User
from app.models.enums import (
    LogAction,
    PassStatus,
    PassType,
    Role,
    StudentStatus,
)

# Enum type name in the database -> the Python enum that must match it.
EXPECTED_ENUMS = {
    "Role": Role,
    "PassType": PassType,
    "PassStatus": PassStatus,
    "LogAction": LogAction,
    "StudentStatus": StudentStatus,
}

OK = "  [ok]  "
BAD = "  [!!]  "
INFO = "  [--]  "

problems: List[str] = []
notes: List[str] = []


def fail(message: str) -> None:
    problems.append(message)
    print(BAD + message)


def ok(message: str) -> None:
    print(OK + message)


def info(message: str) -> None:
    print(INFO + message)


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def check_connection(engine) -> bool:
    heading("1. Connection")
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                version = connection.execute(text("SHOW server_version")).scalar()
                ok(f"connected to PostgreSQL {version}")
            elif engine.dialect.name == "sqlite":
                version = connection.execute(
                    text("select sqlite_version()")
                ).scalar()
                ok(f"connected to SQLite {version}")
            else:
                ok(f"connected ({engine.dialect.name})")
        return True
    except SQLAlchemyError as error:
        fail(f"cannot connect: {_short(error)}")
        return False


def check_tables(engine) -> Dict[str, bool]:
    heading("2. Tables")
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    found = {}
    for table_name in Base.metadata.tables:
        if table_name in present:
            ok(f"'{table_name}' exists")
            found[table_name] = True
        else:
            fail(f"'{table_name}' is MISSING")
            found[table_name] = False
    return found


def check_columns(engine, tables_found: Dict[str, bool]) -> None:
    heading("3. Columns")
    inspector = inspect(engine)

    for table_name, table in Base.metadata.tables.items():
        if not tables_found.get(table_name):
            info(f"'{table_name}' skipped (table missing)")
            continue

        actual = {column["name"]: column for column in inspector.get_columns(table_name)}
        expected = set(table.columns.keys())

        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)

        if missing:
            fail(f"'{table_name}' is missing column(s): {', '.join(missing)}")
        else:
            ok(f"'{table_name}' has all {len(expected)} expected columns")

        if extra:
            # Not an error: the application simply ignores columns it does not map.
            notes.append(
                f"'{table_name}' has extra column(s) the app does not use: "
                f"{', '.join(extra)}"
            )
            info(f"'{table_name}' extra column(s) ignored: {', '.join(extra)}")


def check_enum_types(engine) -> None:
    heading("4. Enum types")

    if engine.dialect.name != "postgresql":
        info(
            f"{engine.dialect.name} has no native enum types - values are stored "
            "as text and validated by the application"
        )
        return

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT t.typname AS type_name, e.enumlabel AS label
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                ORDER BY t.typname, e.enumsortorder
                """
            )
        ).all()

    actual: Dict[str, List[str]] = {}
    for type_name, label in rows:
        actual.setdefault(type_name, []).append(label)

    for type_name, enum_cls in EXPECTED_ENUMS.items():
        expected_labels = {member.value for member in enum_cls}
        if type_name not in actual:
            fail(f"enum type \"{type_name}\" does not exist")
            continue

        found_labels = set(actual[type_name])
        missing = sorted(expected_labels - found_labels)
        if missing:
            # This is the failure mode that silently breaks writes, e.g. a
            # database still carrying 'checked in' instead of 'checked_in'.
            fail(
                f'enum "{type_name}" is missing value(s): {", ".join(missing)} '
                f"(database has: {', '.join(sorted(found_labels))})"
            )
        else:
            ok(f'enum "{type_name}" has all expected values')
            spare = sorted(found_labels - expected_labels)
            if spare:
                info(f'  "{type_name}" also allows unused value(s): {", ".join(spare)}')


def check_data(engine, tables_found: Dict[str, bool]) -> None:
    heading("5. Existing data (read-only)")

    if not all(tables_found.values()):
        info("skipped (not every table is present)")
        return

    from sqlalchemy.orm import Session

    try:
        with Session(engine) as session:
            for label, model in (
                ("users", User),
                ("leave_pass", LeavePass),
                ("logs", Log),
            ):
                count = session.scalar(select(func.count()).select_from(model))
                ok(f"{label}: {count} row(s)")

            # Hydrating one row proves the mapping really works end to end -
            # enum decoding included.
            sample = session.scalars(select(User).limit(1)).first()
            if sample is None:
                info("no user rows yet, so the ORM mapping could not be exercised")
            else:
                ok(
                    f"ORM read works (sample user role decoded as "
                    f"'{getattr(sample.role, 'value', sample.role)}')"
                )

            roles = session.execute(
                select(User.role, func.count()).group_by(User.role)
            ).all()
            if roles:
                breakdown = ", ".join(
                    f"{getattr(role, 'value', role)}={count}" for role, count in roles
                )
                info(f"users by role: {breakdown}")
    except SQLAlchemyError as error:
        fail(f"reading existing data failed: {_short(error)}")


def check_settings() -> None:
    heading("6. Configuration")

    if len(settings.SECRET_KEY) < 32:
        fail("SECRET_KEY is shorter than 32 characters")
    elif "change-me" in settings.SECRET_KEY or "dev-only" in settings.SECRET_KEY:
        fail("SECRET_KEY is still the placeholder from .env.example")
    else:
        ok(f"SECRET_KEY looks strong ({len(settings.SECRET_KEY)} chars)")

    if not settings.DEFAULT_PASSWORD or "replace" in settings.DEFAULT_PASSWORD:
        fail("DEFAULT_PASSWORD is still a placeholder")
    else:
        ok("DEFAULT_PASSWORD is set")

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        ok(f"Supabase storage configured (bucket '{settings.SUPABASE_BUCKET}')")
    else:
        info(
            "Supabase not configured - student photos will be stored in "
            f"'{settings.LOCAL_UPLOAD_DIR}/' and served from /uploads"
        )

    ok(f"CORS allows: {', '.join(settings.CORS_ORIGINS)}")

    if settings.CREATE_TABLES_ON_STARTUP:
        info(
            "CREATE_TABLES_ON_STARTUP is on (emits CREATE TABLE IF NOT EXISTS; "
            "safe, but you can turn it off once this check passes)"
        )


def _short(error: Exception, limit: int = 300) -> str:
    message = str(error).split("\n")[0]
    return message[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        help="Database URL to test instead of the configured DATABASE_URL",
    )
    args = parser.parse_args()

    url = args.url or settings.DATABASE_URL
    # Never print the password back out.
    from sqlalchemy.engine import make_url

    safe_url = make_url(url).render_as_string(hide_password=True)

    print("DigiPass database check")
    print("=" * 23)
    print(f"target: {safe_url}")

    engine = create_engine(url, pool_pre_ping=True)
    try:
        if check_connection(engine):
            tables_found = check_tables(engine)
            check_columns(engine, tables_found)
            check_enum_types(engine)
            check_data(engine, tables_found)
        check_settings()
    finally:
        engine.dispose()

    heading("Result")
    if problems:
        print(f"{len(problems)} problem(s) need attention:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("All checks passed - the backend can run against this database.")
    if notes:
        print()
        print("Notes (not problems):")
        for note in notes:
            print(f"  - {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
