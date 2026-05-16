from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.models.appToken import AppToken
from app.services.metricEvent import MetricEventService
from app.db.database import get_db
from app.utils.user import get_current_user, require_admin_role

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(get_current_user)],
)


def get_app_token_or_404(
    app_token_id: int = Query(
        ..., gt=0, description="ID of the app token whose metrics to query"
    ),
    db: Session = Depends(get_db),
) -> AppToken:
    token = db.get(AppToken, app_token_id)
    if not token:
        raise HTTPException(status_code=404, detail="App token not found")
    return token


@router.get("/summary")
def get_metrics_summary(
    time_range_days: Optional[int] = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to look back for metrics",
    ),
    include_trends: bool = Query(
        False, description="Include day-over-day trend analysis"
    ),
    db: Session = Depends(get_db),
    app_token: AppToken = Depends(get_app_token_or_404),
) -> Dict[str, Any]:
    """
    Aggregated metrics summary for the given app token.
    """
    service = MetricEventService(db)

    try:
        summary = service.get_metrics_summary(app_token.id, time_range_days)
        # TODO: implement get_metrics_summary_with_trends; for now expose a
        # placeholder so the include_trends flag remains a stable contract.
        if include_trends:
            summary = {**summary, "trends": None}

        return {"status": "success", "data": summary}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating metrics summary: {str(e)}",
        )


@router.get("/screens")
def get_top_screens(
    limit: int = Query(
        10, ge=1, le=50, description="Number of top screens to return (max 50)"
    ),
    time_range_days: Optional[int] = Query(
        30, ge=1, le=365, description="Number of days to look back for metrics"
    ),
    method: str = Query(
        "join",
        pattern="^(join|direct)$",
        description="Calculation method: 'join' (pair events) or 'direct' (use duration from attributes)",
    ),
    db: Session = Depends(get_db),
    app_token: AppToken = Depends(get_app_token_or_404),
) -> Dict[str, Any]:
    """
    Top most-visited screens ranked by average time spent.
    """
    service = MetricEventService(db)

    try:
        if method == "direct":
            top_screens = service.get_top_screens_alternative_method(
                app_token.id, limit, time_range_days
            )
        else:
            top_screens = service.get_top_screens(
                app_token.id, limit, time_range_days
            )

        if not top_screens:
            return {
                "status": "success",
                "data": [],
                "message": "No screen visit data found for the specified time range",
            }

        return {
            "status": "success",
            "data": top_screens,
            "metadata": {
                "limit": limit,
                "time_range_days": time_range_days,
                "calculation_method": method,
                "total_screens_found": len(top_screens),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating top screens: {str(e)}",
        )


@router.get("/http")
def get_http_performance_overview(
    time_range_days: Optional[int] = Query(
        30,
        ge=1,
        le=90,
        description="Number of days to look back for HTTP metrics (max 90 days)",
    ),
    include_timeline: bool = Query(
        False, description="Include timeline data for trend analysis"
    ),
    interval_hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Interval in hours for timeline data (if include_timeline=true)",
    ),
    db: Session = Depends(get_db),
    app_token: AppToken = Depends(get_app_token_or_404),
) -> Dict[str, Any]:
    """
    HTTP performance overview for the given app token.
    """
    service = MetricEventService(db)

    try:
        overview = service.get_http_performance_overview(
            app_token.id, time_range_days
        )
        overview["time_range_days"] = time_range_days

        return {"status": "success", "data": overview}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating HTTP performance: {str(e)}",
        )


@router.get("/crashes")
def get_crash_timeline(
    time_range_days: Optional[int] = Query(
        30, ge=1, le=365, description="Number of days to look back for crash data"
    ),
    db: Session = Depends(get_db),
    app_token: AppToken = Depends(get_app_token_or_404),
) -> Dict[str, Any]:
    """
    Crash events grouped by day for timeline visualization.
    """
    service = MetricEventService(db)

    try:
        timeline = service.get_crash_timeline(app_token.id, time_range_days)
        summary = service.get_crash_summary(app_token.id, time_range_days)

        trend = None
        if time_range_days >= 14:
            now = datetime.utcnow()
            recent_period_start = now - timedelta(days=7)
            previous_period_end = recent_period_start
            previous_period_start = previous_period_end - timedelta(days=7)

            recent_crashes = sum(
                item["crash_count"]
                for item in timeline
                if datetime.fromisoformat(item["date"]) >= recent_period_start
            )

            previous_crashes = sum(
                item["crash_count"]
                for item in timeline
                if previous_period_start
                <= datetime.fromisoformat(item["date"])
                < previous_period_end
            )

            if previous_crashes > 0:
                trend_percent = (
                    (recent_crashes - previous_crashes) / previous_crashes
                ) * 100
                trend = {
                    "period": "last_7_days_vs_previous",
                    "change_percent": round(trend_percent, 2),
                    "direction": "up"
                    if trend_percent > 0
                    else "down"
                    if trend_percent < 0
                    else "stable",
                }
            else:
                trend = {
                    "period": "last_7_days_vs_previous",
                    "change_percent": 100.0 if recent_crashes > 0 else 0,
                    "direction": "up" if recent_crashes > 0 else "stable",
                }

        return {
            "status": "success",
            "data": {
                "timeline": timeline,
                "summary": summary,
                "trend": trend,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating crash timeline: {str(e)}",
        )


@router.get("/devices")
def get_device_breakdown(
    limit: int = Query(
        20, ge=1, le=100, description="Number of devices to return per page"
    ),
    offset: int = Query(
        0, ge=0, description="Number of devices to skip (for pagination)"
    ),
    time_range_days: Optional[int] = Query(
        30, ge=1, le=365, description="Number of days to look back for device metrics"
    ),
    sort_by: str = Query(
        "sessions",
        pattern="^(sessions|crashes|avg_memory_mb|device_id)$",
        description="Field to sort by",
    ),
    sort_order: str = Query(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order (ascending or descending)",
    ),
    db: Session = Depends(get_db),
    app_token: AppToken = Depends(get_app_token_or_404),
) -> Dict[str, Any]:
    """
    Breakdown by device_id with sessions, crashes, and avg memory usage.
    """
    service = MetricEventService(db)

    try:
        devices, total_count = service.get_device_breakdown(
            app_token.id,
            limit,
            offset,
            time_range_days,
            sort_by,
            sort_order,
        )

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
                "has_previous": offset > 0,
            },
            "metadata": {
                "time_range_days": time_range_days,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating device breakdown: {str(e)}",
        )


@router.delete("/session/{session_id}")
def delete_session_events(
    session_id: str = Path(..., description="Session ID to delete all metric events for"),
    db: Session = Depends(get_db),
    app_token: AppToken = Depends(get_app_token_or_404),
    _admin = Depends(require_admin_role),
) -> Dict[str, Any]:
    """
    Hard-delete all metric events for a given session_id under the
    specified app token. **Admin role required** (currently always 403
    until the role column is added).
    """
    service = MetricEventService(db)

    try:
        result = service.delete_session_events(app_token.id, session_id)

        if result["deleted_count"] == 0 and "not found" in result["message"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found for app token {app_token.id}",
            )

        return {"status": "success", "data": result}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting session events: {str(e)}",
        )
