from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.models.appToken import AppToken 
from app.services.metricEvent import MetricEventService
from app.db.database import get_db 
from app.utils.user import get_current_user, require_admin_role 
from app.utils.jwt import verify_token

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(verify_token)])

@router.get("/summary")
async def get_metrics_summary(
    time_range_days: Optional[int] = Query(
        30, 
        ge=1, 
        le=365,
        description="Number of days to look back for metrics"
    ),
    include_trends: bool = Query(
        False,
        description="Include day-over-day trend analysis"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Assuming you have auth
) -> Dict[str, Any]:
    """
    Get aggregated metrics summary for the authenticated user's app token.
    
    Returns:
        - total_sessions: Total number of unique sessions
        - avg_session_duration_seconds: Average session duration in seconds
        - total_crashes: Number of crash events
        - avg_app_start_time_ms: Average app start time in milliseconds
        - Optional trends if include_trends=true
    """
    
    # Get the user's app token (assuming one app token per user for simplicity)
    # Adjust this based on your authentication logic
    app_token = db.query(AppToken).filter(
        AppToken.user_id == current_user.id  # Assuming user_id in AppToken
    ).first()
    
    if not app_token:
        raise HTTPException(
            status_code=404,
            detail="No app token found for authenticated user"
        )
    
    service = MetricEventService(db)
    
    try:
        if include_trends:
            summary = service.get_metrics_summary_with_trends(
                app_token.id,
                time_range_days
            )
        else:
            summary = service.get_metrics_summary(
                app_token.id,
                time_range_days
            )
        
        return {
            "status": "success",
            "data": summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating metrics summary: {str(e)}"
        )

@router.get("/screens")
async def get_top_screens(
    limit: int = Query(
        10, 
        ge=1, 
        le=50,
        description="Number of top screens to return (max 50)"
    ),
    time_range_days: Optional[int] = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to look back for metrics"
    ),
    method: str = Query(
        "join",
        pattern="^(join|direct)$",
        description="Calculation method: 'join' (pair events) or 'direct' (use duration from attributes)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get top 10 most-visited screens ranked by average time spent.
    
    Returns for each screen:
        - screen_name: Name of the screen/page
        - visit_count: Number of times the screen was visited
        - avg_duration_ms: Average time spent on the screen in milliseconds
    
    The endpoint ranks screens by average duration (highest first),
    but also provides visit_count for context.
    """
    
    # Get user's app token
    app_token = db.query(AppToken).filter(
        AppToken.user_id == current_user.id
    ).first()
    
    if not app_token:
        raise HTTPException(
            status_code=404,
            detail="No app token found for authenticated user"
        )
    
    service = MetricEventService(db)
    
    try:
        # Choose calculation method
        if method == "direct":
            top_screens = service.get_top_screens_alternative_method(
                app_token.id,
                limit,
                time_range_days
            )
        else:
            top_screens = service.get_top_screens(
                app_token.id,
                limit,
                time_range_days
            )
        
        if not top_screens:
            return {
                "status": "success",
                "data": [],
                "message": "No screen visit data found for the specified time range"
            }
        
        return {
            "status": "success",
            "data": top_screens,
            "metadata": {
                "limit": limit,
                "time_range_days": time_range_days,
                "calculation_method": method,
                "total_screens_found": len(top_screens)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating top screens: {str(e)}"
        )
    
@router.get("/http")
async def get_http_performance_overview(
    time_range_days: Optional[int] = Query(
        30,
        ge=1,
        le=90,
        description="Number of days to look back for HTTP metrics (max 90 days)"
    ),
    include_timeline: bool = Query(
        False,
        description="Include timeline data for trend analysis"
    ),
    interval_hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Interval in hours for timeline data (if include_timeline=true)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get HTTP performance overview for the authenticated user's app.
    
    Returns comprehensive HTTP metrics including:
    - Total requests
    - Error rate (4xx/5xx responses)
    - Average response time
    - P95 and P99 response times
    - Top endpoints by request count with their performance metrics
    
    Optional timeline data for visualizing trends over time.
    """
    
    # Get user's app token
    app_token = db.query(AppToken).filter(
        AppToken.user_id == current_user.id
    ).first()
    
    if not app_token:
        raise HTTPException(
            status_code=404,
            detail="No app token found for authenticated user"
        )
    
    service = MetricEventService(db)
    
    try:
        # Get overview metrics
        overview = service.get_http_performance_overview(
            app_token.id,
            time_range_days
        )
        
        overview["time_range_days"] = time_range_days
        
        response_data = overview
        
        return {
            "status": "success",
            "data": response_data,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating HTTP performance: {str(e)}"
        )


@router.get("/crashes")
async def get_crash_timeline(
    time_range_days: Optional[int] = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to look back for crash data"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get crash timeline with crash events grouped by day.
    
    Returns chronological list of dates with crash counts,
    including dates with zero crashes for complete timeline visualization.
    """
    
    # Get user's app token
    app_token = db.query(AppToken).filter(
        AppToken.user_id == current_user.id
    ).first()
    
    if not app_token:
        raise HTTPException(
            status_code=404,
            detail="No app token found for authenticated user"
        )
    
    service = MetricEventService(db)
    
    try:
        # Get crash timeline
        timeline = service.get_crash_timeline(
            app_token.id,
            time_range_days
        )
        
        # Get summary statistics
        summary = service.get_crash_summary(
            app_token.id,
            time_range_days
        )
        
        # Calculate trend (compare last 7 days to previous 7 days)
        trend = None
        if time_range_days >= 14:
            now = datetime.utcnow()
            recent_period_start = now - timedelta(days=7)
            previous_period_end = recent_period_start
            previous_period_start = previous_period_end - timedelta(days=7)
            
            recent_crashes = sum(
                item['crash_count'] for item in timeline
                if datetime.fromisoformat(item['date']) >= recent_period_start
            )
            
            previous_crashes = sum(
                item['crash_count'] for item in timeline
                if previous_period_start <= datetime.fromisoformat(item['date']) < previous_period_end
            )
            
            if previous_crashes > 0:
                trend_percent = ((recent_crashes - previous_crashes) / previous_crashes) * 100
                trend = {
                    "period": "last_7_days_vs_previous",
                    "change_percent": round(trend_percent, 2),
                    "direction": "up" if trend_percent > 0 else "down" if trend_percent < 0 else "stable"
                }
            else:
                trend = {
                    "period": "last_7_days_vs_previous",
                    "change_percent": 100.0 if recent_crashes > 0 else 0,
                    "direction": "up" if recent_crashes > 0 else "stable"
                }
        
        return {
            "status": "success",
            "data": {
                "timeline": timeline,
                "summary": summary,
                "trend": trend
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating crash timeline: {str(e)}"
        )
    
@router.get("/devices")
async def get_device_breakdown(
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of devices to return per page"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of devices to skip (for pagination)"
    ),
    time_range_days: Optional[int] = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to look back for device metrics"
    ),
    sort_by: str = Query(
        "sessions",
        pattern="^(sessions|crashes|avg_memory_mb|device_id)$",
        description="Field to sort by"
    ),
    sort_order: str = Query(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order (ascending or descending)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get breakdown by device_id with sessions, crashes, and average memory usage.
    
    Returns paginated list of devices with:
    - device_id: Unique device identifier
    - sessions: Total number of sessions for this device
    - crashes: Total number of crashes on this device
    - avg_memory_mb: Average memory usage in megabytes
    
    Useful for identifying problematic devices or understanding usage patterns.
    """
    
    # Get user's app token
    app_token = db.query(AppToken).filter(
        AppToken.user_id == current_user.id
    ).first()
    
    if not app_token:
        raise HTTPException(
            status_code=404,
            detail="No app token found for authenticated user"
        )
    
    service = MetricEventService(db)
    
    try:
        # Get device breakdown with pagination
        devices, total_count = service.get_device_breakdown(
            app_token.id,
            limit,
            offset,
            time_range_days,
            sort_by,
            sort_order
        )
        
        # Calculate pagination metadata
        page = (offset // limit) + 1 if limit > 0 else 1
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        
        return {
            "status": "success",
            "data": devices,
            "pagination": {
                "total_devices": total_count,
                "limit": limit,
                "offset": offset,
                "page": page,
                "total_pages": total_pages,
                "has_next": offset + limit < total_count,
                "has_previous": offset > 0
            },
            "metadata": {
                "time_range_days": time_range_days,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating device breakdown: {str(e)}"
        )
    
@router.delete("/session/{session_id}")
async def delete_session_events(
    session_id: str = Path(..., description="Session ID to delete all metric events for"),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role)  # Admin role only
) -> Dict[str, Any]:
    """
    Hard-delete all metric events for a given session_id.
    
    **Admin role required.**
    
    This endpoint permanently removes all metric events associated with the
    specified session_id from the database. This operation cannot be undone.
    
    Args:
        session_id: The session ID to delete events for
    
    Returns:
        Deletion summary including count of deleted events
    
    Raises:
        403: If user is not an admin
        404: If session not found for the user's app token
        500: If deletion fails
    """
    
    # Get user's app token (assuming one app token per user)
    app_token = db.query(AppToken).filter(
        AppToken.user_id == current_user.id
    ).first()
    
    if not app_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No app token found for authenticated user"
        )
    
    service = MetricEventService(db)
    
    try:
        # Delete session events
        result = service.delete_session_events(
            app_token.id,
            session_id
        )
        
        if result["deleted_count"] == 0 and "not found" in result["message"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found for your app token"
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting session events: {str(e)}"
        )