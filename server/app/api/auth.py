import hmac
import secrets
import time
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.config import settings

ACTIVE_SESSIONS: Dict[str, float] = {}
LOGIN_ATTEMPTS: Dict[str, List[float]] = {}
SESSION_TTL_SECONDS = 7 * 24 * 3600
MAX_ATTEMPTS_PER_WINDOW = 5
ATTEMPT_WINDOW_SECONDS = 300


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    token: str
    username: str
    expires_at: float


class AuthStatusResponse(BaseModel):
    authenticated: bool
    username: str


def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    attempts = LOGIN_ATTEMPTS.get(client_ip, [])
    valid_attempts = [t for t in attempts if now - t < ATTEMPT_WINDOW_SECONDS]
    LOGIN_ATTEMPTS[client_ip] = valid_attempts
    return len(valid_attempts) < MAX_ATTEMPTS_PER_WINDOW


def record_failed_attempt(client_ip: str) -> None:
    attempts = LOGIN_ATTEMPTS.setdefault(client_ip, [])
    attempts.append(time.time())


def clear_failed_attempts(client_ip: str) -> None:
    LOGIN_ATTEMPTS.pop(client_ip, None)


def verify_credentials(username: str, password: str) -> bool:
    if not username or not password:
        return False
    user_ok = hmac.compare_digest(username.strip(), settings.admin_user)
    pass_ok = hmac.compare_digest(password, settings.admin_pass)
    return user_ok and pass_ok


def create_token() -> str:
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
    return token


def validate_token(token: Optional[str]) -> bool:
    if not token:
        return False
    clean = token.replace("Bearer ", "").strip()
    exp = ACTIVE_SESSIONS.get(clean)
    if not exp:
        return False
    if time.time() > exp:
        ACTIVE_SESSIONS.pop(clean, None)
        return False
    return True


def revoke_token(token: Optional[str]) -> None:
    if not token:
        return
    clean = token.replace("Bearer ", "").strip()
    ACTIVE_SESSIONS.pop(clean, None)


def require_auth(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> bool:
    candidate = authorization or x_auth_token or token
    if not candidate or not validate_token(candidate):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


auth_router = APIRouter(prefix="/api/auth")


@auth_router.post("/login", response_model=LoginResponse)
async def api_login(req: LoginRequest, request: Request) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 5 minutes.",
        )

    if not verify_credentials(req.username, req.password):
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    clear_failed_attempts(client_ip)
    token = create_token()
    return LoginResponse(
        status="ok",
        token=token,
        username=settings.admin_user,
        expires_at=ACTIVE_SESSIONS[token],
    )


@auth_router.post("/logout")
async def api_logout(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Dict[str, str]:
    candidate = authorization or x_auth_token or token
    if candidate:
        revoke_token(candidate)
    return {"status": "logged_out"}


@auth_router.get("/verify", response_model=AuthStatusResponse)
async def api_verify(authenticated: bool = Depends(require_auth)) -> AuthStatusResponse:
    return AuthStatusResponse(
        authenticated=True,
        username=settings.admin_user,
    )
