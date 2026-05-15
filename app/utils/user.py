from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Callable
from functools import wraps

from app.utils.jwt import verify_token
from app.models.user import User

security = HTTPBearer()

async def get_current_user(payload: dict = Depends(verify_token)):
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    user = User.get_by_id(user_id)  
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

def require_admin_role(current_user: User = Depends(get_current_user)):
    """
    Dependency to verify that the current user has admin role.
    Usage: admin: User = Depends(require_admin_role)
    """
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation"
        )
    return current_user

# Alternative: Higher-order function for role checking
def require_role(required_role: str):
    """
    Create a dependency that requires a specific role.
    
    Usage: 
    @app.get("/admin")
    async def admin_endpoint(user: User = Depends(require_role("admin"))):
        ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if not hasattr(current_user, 'role') or current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required_role.capitalize()} role required for this operation"
            )
        return current_user
    return role_checker

# Alternative: Decorator for role checking
def admin_required(func: Callable):
    """
    Decorator to require admin role on endpoint functions.
    
    Usage:
    @app.get("/admin")
    @admin_required
    async def admin_endpoint(current_user: User = Depends(get_current_user)):
        ...
    """
    @wraps(func)
    async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required for this operation"
            )
        return await func(*args, current_user=current_user, **kwargs)
    return wrapper

# Example User model (replace with your actual model)
class User:
    def __init__(self, id: int, username: str, role: str):
        self.id = id
        self.username = username
        self.role = role