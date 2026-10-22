"""Authentication dependency for administrative routes in SOLANA PREDATOR."""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from backend.config import settings

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


def require_admin_auth(
    key_from_header: str = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials = Security(bearer_auth),
) -> bool:
    """Validate admin API token from header or bearer token."""
    token = key_from_header or (credentials.credentials if credentials else None)
    if not token or token != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid X-Admin-Key or Bearer token required for administrative mutations",
        )
    return True
