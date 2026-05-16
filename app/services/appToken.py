from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List
import secrets
from datetime import datetime

from app.models.appToken import AppToken
from app.models.user import User
from app.utils.hashing import hash_token
from app.models.metricEvent import MetricEvent


class AppTokenService:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_token(self, user_id: int, label: str) -> dict:
        """
        Generate a new app token for a user
        Returns the raw token (to show once) and the created token object
        """
        # Check if user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate raw token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_token)  # Hash the token for storage
        
        # Create token record
        db_token = AppToken(
            user_id=user_id,
            token_hash=token_hash,
            label=label
        )
        
        try:
            self.db.add(db_token)
            self.db.commit()
            self.db.refresh(db_token)
            
            # Return the raw token (only shown once!)
            return {
                "token": raw_token,
                "token_id": db_token.id,
                "label": db_token.label,
                "created_at": db_token.created_at
            }
        except SQLAlchemyError as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create token: {str(e)}")
    
    def get_user_tokens(self, user_id: int, skip: int = 0, limit: int = 100) -> List[AppToken]:
        """Get all tokens for a specific user"""
        tokens = self.db.query(AppToken).filter(
            AppToken.user_id == user_id
        ).offset(skip).limit(limit).all()
        
        return tokens
    
    def get_token_by_id(self, token_id: int, user_id: int) -> Optional[AppToken]:
        """Get a specific token by ID (with ownership check)"""
        token = self.db.query(AppToken).filter(
            AppToken.id == token_id,
            AppToken.user_id == user_id
        ).first()
        
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
        
        return token
    
    def revoke_token(self, token_id: int, user_id: int) -> dict:
        """Revoke/delete an app token"""
        token = self.get_token_by_id(token_id, user_id)
        
        try:
            self.db.delete(token)
            self.db.commit()
            return {"message": "Token revoked successfully", "token_id": token_id}
        except SQLAlchemyError as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to revoke token: {str(e)}")
    
    def revoke_all_user_tokens(self, user_id: int) -> dict:
        """Revoke all tokens for a specific user"""
        try:
            deleted_count = self.db.query(AppToken).filter(
                AppToken.user_id == user_id
            ).delete()
            self.db.commit()
            return {"message": f"Revoked {deleted_count} tokens", "count": deleted_count}
        except SQLAlchemyError as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to revoke tokens: {str(e)}")
    
    def validate_token(self, token: str) -> Optional[AppToken]:
        """
        Validate a raw token and return the token object if valid
        Used for authenticating API requests
        """
        token_hash = hash_token(token)
        
        db_token = self.db.query(AppToken).filter(
            AppToken.token_hash == token_hash
        ).first()
        
        if not db_token:
            return None
        
        # You could add additional validation here:
        # - Check if token is expired
        # - Check if token is revoked
        
        return db_token
    
    def get_token_stats(self, token_id: int, user_id: int) -> dict:
        """Get statistics for a specific token"""
        token = self.get_token_by_id(token_id, user_id)
        
        event_count = self.db.query(MetricEvent).filter(
            MetricEvent.app_token_id == token_id
        ).count()
        
        return {
            "token_id": token_id,
            "label": token.label,
            "created_at": token.created_at,
            "total_events": event_count,
            "is_active": True  # Add logic if you have is_active field
        }