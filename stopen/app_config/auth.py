"""简单认证中间件 — Bearer Token"""
import json
import secrets
from pathlib import Path

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

AUTH_FILE = Path(__file__).resolve().parent.parent / "storage" / ".auth_secret"


def _load_or_create_secret() -> str:
    if AUTH_FILE.exists():
        return AUTH_FILE.read_text().strip()
    token = secrets.token_hex(32)
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(token)
    Path(AUTH_FILE.parent / "auth_config.json").write_text(json.dumps({"token": token}))
    return token


class AuthMiddleware(BaseHTTPMiddleware):
    """所有 /api/* 路由需要 Bearer Token 认证，静态文件和前端页面放行"""

    def __init__(self, app):
        super().__init__(app)
        self._token = _load_or_create_secret()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 放行前端资源（.html, .js, .css, 图片等）
        if not path.startswith("/api/"):
            return await call_next(request)

        # /api/health 和 /api/auth/* 放行
        if path == "/api/health" or path.startswith("/api/auth/"):
            return await call_next(request)

        # 其他 /api/* 需要 Bearer Token
        auth = request.headers.get("Authorization", "")
        if auth.replace("Bearer ", "").strip() != self._token:
            raise HTTPException(401, "未认证：需要有效的 Bearer Token")

        return await call_next(request)
