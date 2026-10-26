"""``POST /login/`` - the only unauthenticated endpoint.

The router does three things and nothing else: declare the path, bind the
request/response schemas, and delegate to :class:`AuthService`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/login", tags=["Login"])


@router.post("/", response_model=LoginResponse)
@router.post("", response_model=LoginResponse, include_in_schema=False)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Exchange college id + password for a bearer token.

    The React client calls ``/login/`` with a JSON body; the second decorator
    accepts ``/login`` as well so neither spelling 307-redirects.
    """
    return AuthService(db).login(request)
