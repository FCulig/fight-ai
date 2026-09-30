from typing import Optional

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from app.models.user import User, UserResponse
from app.services import user_service
from app.utils.auth import current_user, get_config, safe_next

router = APIRouter()

_config = get_config()
oauth = OAuth()
oauth.register(
    "google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=_config.google_client_id,
    client_secret=_config.google_client_secret,
    client_kwargs={"scope": "openid email profile"},
)


def _to_app(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


@router.get("/login")
async def login(request: Request, next: Optional[str] = None):
    """A full-page navigation, not a fetch: the SPA sends the browser here."""
    request.session["next"] = safe_next(next)
    return await oauth.google.authorize_redirect(
        request, _config.callback_url, prompt="select_account",
    )


@router.get("/callback")
async def callback(request: Request):
    next_path = safe_next(request.session.pop("next", None))
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return _to_app("/?auth_error=failed")

    info = token.get("userinfo") or {}
    if not info.get("email") or not info.get("email_verified"):
        return _to_app("/?auth_error=unverified")

    user = await run_in_threadpool(user_service.sign_in, info["email"], info.get("name"))
    request.session.clear()
    if not user.is_active:
        return _to_app("/?auth_error=disabled")
    request.session["uid"] = user.id
    return _to_app(next_path)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()
    return Response(status_code=204)
