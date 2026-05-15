from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, desc
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from app.models.metricEvent import MetricEvent  
import json

class MetricEventService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_metrics_summary(
        self, 
        app_token_id: int,
        time_range_days: Optional[int] = 30
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics summary for an app token
        
        Returns:
            Dict containing:
            - total_sessions: Total number of unique sessions
            - avg_session_duration_seconds: Average session duration in seconds
            - total_crashes: Number of crash events
            - avg_app_start_time_ms: Average app start time in milliseconds
        """
        
        # Base query filter
        base_filter = MetricEvent.app_token_id == app_token_id
        
        # Add time range filter if specified
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(
                base_filter,
                MetricEvent.created_at >= time_threshold
            )
        
        # 1. Total sessions (unique session_id)
        total_sessions_query = self.db.query(
            func.count(func.distinct(MetricEvent.session_id))
        ).filter(base_filter)
        total_sessions = total_sessions_query.scalar() or 0
        
        # 2. Average session duration
        # We need to calculate session duration from session_start and session_end events
        # Assuming session_start and session_end events exist
        session_durations = self.db.query(
            MetricEvent.session_id,
            func.max(
                case(
                    (MetricEvent.event_type == 'session_end', MetricEvent.created_at),
                    else_=None
                )
            ).label('end_time'),
            func.min(
                case(
                    (MetricEvent.event_type == 'session_start', MetricEvent.created_at),
                    else_=None
                )
            ).label('start_time')
        ).filter(
            and_(
                base_filter,
                MetricEvent.event_type.in_(['session_start', 'session_end'])
            )
        ).group_by(MetricEvent.session_id).subquery()
        
        avg_duration_query = self.db.query(
            func.avg(
                func.extract('epoch', session_durations.c.end_time - session_durations.c.start_time)
            )
        ).filter(
            session_durations.c.start_time.isnot(None),
            session_durations.c.end_time.isnot(None)
        )
        
        avg_session_duration = avg_duration_query.scalar() or 0.0
        
        # 3. Total crashes
        total_crashes_query = self.db.query(
            func.count(MetricEvent.id)
        ).filter(
            and_(
                base_filter,
                MetricEvent.event_type == 'crash'
            )
        )
        total_crashes = total_crashes_query.scalar() or 0
        
        # 4. Average app start time (in milliseconds)
        # Assuming app_start events have value field containing start time in ms
        avg_start_time_query = self.db.query(
            func.avg(func.cast(MetricEvent.value, func.Float))
        ).filter(
            and_(
                base_filter,
                MetricEvent.event_type == 'app_start',
                MetricEvent.value.isnot(None)
            )
        )
        avg_app_start_time_ms = avg_start_time_query.scalar() or 0.0
        
        return {
            "total_sessions": total_sessions,
            "avg_session_duration_seconds": round(avg_session_duration, 2),
            "total_crashes": total_crashes,
            "avg_app_start_time_ms": round(avg_app_start_time_ms, 2),
            "time_range_days": time_range_days
        }
    
    def get_top_screens(
        self,
        app_token_id: int,
        limit: int = 10,
        time_range_days: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """
        Get top most-visited screens ranked by average time spent.
        
        Assumptions:
        - Screen view events have event_type = 'screen_view'
        - Screen name is stored in attributes.screen_name or attributes.screen
        - Screen exit events have event_type = 'screen_exit'
        - Time spent is calculated as (screen_exit_time - screen_enter_time)
        - If no exit event, time spent is not counted (incomplete session)
        
        Returns:
            List of dicts with:
            - screen_name: Name of the screen
            - visit_count: Number of times screen was visited
            - avg_duration_ms: Average time spent on screen in milliseconds
        """
        
        # Base filter for time range
        base_filter = and_(
            MetricEvent.app_token_id == app_token_id,
            MetricEvent.event_type.in_(['screen_view', 'screen_exit'])
        )
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(
                base_filter,
                MetricEvent.created_at >= time_threshold
            )
        
        # Subquery to pair screen_view with screen_exit events
        # Using a window function approach or self-join
        # We'll match each screen_view with its corresponding screen_exit
        
        # First, get all screen_view events with their metadata
        screen_views = self.db.query(
            MetricEvent.id.label('view_id'),
            MetricEvent.session_id,
            MetricEvent.created_at.label('view_time'),
            func.json_extract(MetricEvent.attributes, '$.screen_name').label('screen_name'),
            func.json_extract(MetricEvent.attributes, '$.screen').label('screen_name_alt')
        ).filter(
            and_(
                base_filter,
                MetricEvent.event_type == 'screen_view'
            )
        ).subquery()
        
        # Get screen_exit events
        screen_exits = self.db.query(
            MetricEvent.session_id,
            MetricEvent.created_at.label('exit_time'),
            func.json_extract(MetricEvent.attributes, '$.screen_name').label('exit_screen_name'),
            func.json_extract(MetricEvent.attributes, '$.screen').label('exit_screen_name_alt')
        ).filter(
            and_(
                base_filter,
                MetricEvent.event_type == 'screen_exit'
            )
        ).subquery()
        
        # Join screen_views with the next screen_exit in the same session
        # This is a simplified approach - for production, consider using window functions
        screen_durations = self.db.query(
            func.coalesce(
                screen_views.c.screen_name,
                screen_views.c.screen_name_alt
            ).label('screen_name'),
            func.extract('epoch', screen_exits.c.exit_time - screen_views.c.view_time).label('duration_seconds')
        ).join(
            screen_exits,
            and_(
                screen_views.c.session_id == screen_exits.c.session_id,
                screen_exits.c.exit_time > screen_views.c.view_time
            )
        ).filter(
            screen_exits.c.exit_time.isnot(None),
            screen_views.c.view_time.isnot(None)
        ).subquery()
        
        # Aggregate results
        results = self.db.query(
            screen_durations.c.screen_name,
            func.count(screen_durations.c.screen_name).label('visit_count'),
            func.avg(screen_durations.c.duration_seconds * 1000).label('avg_duration_ms')  # Convert to ms
        ).filter(
            screen_durations.c.screen_name.isnot(None)
        ).group_by(
            screen_durations.c.screen_name
        ).order_by(
            desc('avg_duration_ms')
        ).limit(limit).all()
        
        return [
            {
                "screen_name": row.screen_name,
                "visit_count": row.visit_count,
                "avg_duration_ms": round(row.avg_duration_ms, 2) if row.avg_duration_ms else 0
            }
            for row in results
        ]
    
    def get_top_screens_alternative_method(
        self,
        app_token_id: int,
        limit: int = 10,
        time_range_days: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """
        Alternative method using attributes JSON to store duration directly.
        
        This method assumes that screen_exit events contain the duration
        in the attributes field (e.g., attributes.duration_ms)
        """
        
        base_filter = and_(
            MetricEvent.app_token_id == app_token_id,
            MetricEvent.event_type == 'screen_exit'
        )
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(
                base_filter,
                MetricEvent.created_at >= time_threshold
            )
        
        results = self.db.query(
            func.json_extract(MetricEvent.attributes, '$.screen_name').label('screen_name'),
            func.json_extract(MetricEvent.attributes, '$.screen').label('screen_name_alt'),
            func.count(MetricEvent.id).label('visit_count'),
            func.avg(func.json_extract(MetricEvent.attributes, '$.duration_ms')).label('avg_duration_ms')
        ).filter(
            and_(
                base_filter,
                func.json_extract(MetricEvent.attributes, '$.duration_ms').isnot(None)
            )
        ).group_by(
            func.json_extract(MetricEvent.attributes, '$.screen_name'),
            func.json_extract(MetricEvent.attributes, '$.screen')
        ).order_by(
            desc('avg_duration_ms')
        ).limit(limit).all()
        
        return [
            {
                "screen_name": row.screen_name or row.screen_name_alt or "Unknown",
                "visit_count": row.visit_count,
                "avg_duration_ms": round(row.avg_duration_ms, 2) if row.avg_duration_ms else 0
            }
            for row in results
        ]
    

    def get_http_performance_overview(
        self,
        app_token_id: int,
        time_range_days: Optional[int] = 30
    ) -> Dict[str, Any]:
        """
        Get HTTP performance overview for an app token.
        
        Assumptions:
        - HTTP request events have event_type = 'http_request'
        - HTTP response events have event_type = 'http_response'
        - Or single event_type = 'http_performance' with duration in attributes
        - Duration is stored in value field or attributes.duration_ms
        - Status code in attributes.status_code or attributes.status
        - Endpoint in attributes.url, attributes.endpoint, or attributes.path
        
        Returns:
            Dict containing:
            - total_requests: Total number of HTTP requests
            - error_rate_percent: Percentage of requests with 4xx/5xx status codes
            - avg_response_time_ms: Average response time in milliseconds
            - p95_response_time_ms: 95th percentile response time
            - p99_response_time_ms: 99th percentile response time
            - endpoints: List of top endpoints with their performance metrics
        """
        
        # Base filter
        base_filter = and_(
            MetricEvent.app_token_id == app_token_id,
            MetricEvent.event_type.in_(['http_request', 'http_response', 'http_performance'])
        )
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(base_filter, MetricEvent.created_at >= time_threshold)
        
        # Check if we have separate request/response events or combined performance events
        combined_events_count = self.db.query(func.count(MetricEvent.id)).filter(
            and_(base_filter, MetricEvent.event_type == 'http_performance')
        ).scalar()
        
        if combined_events_count > 0:
            # Use combined performance events
            return self._get_http_performance_from_combined_events(base_filter)
        else:
            # Use separate request/response events
            return self._get_http_performance_from_separate_events(base_filter)
    
    def _get_http_performance_from_combined_events(
        self,
        base_filter
    ) -> Dict[str, Any]:
        """Extract HTTP performance from combined events (single event per request)"""
        
        # Get duration and status code from attributes or value field
        query = self.db.query(
            func.json_extract(MetricEvent.attributes, '$.duration_ms').label('duration_ms'),
            func.json_extract(MetricEvent.attributes, '$.response_time_ms').label('response_time_ms'),
            func.json_extract(MetricEvent.attributes, '$.status_code').label('status_code'),
            func.json_extract(MetricEvent.attributes, '$.status').label('status'),
            func.json_extract(MetricEvent.attributes, '$.url').label('url'),
            func.json_extract(MetricEvent.attributes, '$.endpoint').label('endpoint'),
            func.json_extract(MetricEvent.attributes, '$.path').label('path'),
            func.json_extract(MetricEvent.attributes, '$.method').label('method'),
            MetricEvent.value.label('value_duration')  # Fallback if duration in value field
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'http_performance')
        )
        
        results = query.all()
        
        if not results:
            return self._get_empty_http_overview()
        
        # Extract durations (try multiple sources)
        durations = []
        error_count = 0
        endpoint_data = {}
        
        for row in results:
            # Get duration (priority: duration_ms > response_time_ms > value field)
            duration = None
            if row.duration_ms is not None:
                duration = float(row.duration_ms)
            elif row.response_time_ms is not None:
                duration = float(row.response_time_ms)
            elif row.value_duration:
                try:
                    duration = float(row.value_duration)
                except (ValueError, TypeError):
                    pass
            
            if duration is not None:
                durations.append(duration)
            
            # Get status code
            status_code = row.status_code or row.status
            if status_code:
                try:
                    status_int = int(status_code)
                    if status_int >= 400:
                        error_count += 1
                except (ValueError, TypeError):
                    pass
            
            # Get endpoint
            endpoint = row.endpoint or row.path or row.url or 'unknown'
            method = row.method or 'GET'
            endpoint_key = f"{method} {endpoint}"
            
            if endpoint_key not in endpoint_data:
                endpoint_data[endpoint_key] = {
                    'count': 0,
                    'durations': [],
                    'errors': 0
                }
            
            endpoint_data[endpoint_key]['count'] += 1
            if duration is not None:
                endpoint_data[endpoint_key]['durations'].append(duration)
            if status_code and int(status_code) >= 400:
                endpoint_data[endpoint_key]['errors'] += 1
        
        # Calculate percentiles
        durations_sorted = sorted(durations)
        total_requests = len(durations)
        
        p95_index = int(len(durations_sorted) * 0.95)
        p99_index = int(len(durations_sorted) * 0.99)
        
        avg_response_time = sum(durations) / len(durations) if durations else 0
        p95_response_time = durations_sorted[p95_index] if p95_index < len(durations_sorted) else 0
        p99_response_time = durations_sorted[p99_index] if p99_index < len(durations_sorted) else 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        # Prepare endpoint performance
        endpoints = []
        for endpoint_key, data in endpoint_data.items():
            endpoint_durations = sorted(data['durations'])
            endpoint_p95_index = int(len(endpoint_durations) * 0.95)
            
            endpoints.append({
                'endpoint': endpoint_key,
                'request_count': data['count'],
                'avg_response_time_ms': round(sum(data['durations']) / len(data['durations']), 2) if data['durations'] else 0,
                'p95_response_time_ms': round(endpoint_durations[endpoint_p95_index], 2) if endpoint_p95_index < len(endpoint_durations) else 0,
                'error_rate_percent': round((data['errors'] / data['count'] * 100), 2) if data['count'] > 0 else 0
            })
        
        # Sort by request count and return top 10
        endpoints.sort(key=lambda x: x['request_count'], reverse=True)
        
        return {
            "total_requests": total_requests,
            "error_rate_percent": round(error_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "p95_response_time_ms": round(p95_response_time, 2),
            "p99_response_time_ms": round(p99_response_time, 2),
            "endpoints": endpoints[:10],
            "time_range_days": None  # Will be set by caller
        }
    
    def _get_http_performance_from_separate_events(
        self,
        base_filter
    ) -> Dict[str, Any]:
        """Extract HTTP performance by pairing request and response events"""
        
        # Get request events
        requests = self.db.query(
            MetricEvent.id.label('request_id'),
            MetricEvent.session_id,
            MetricEvent.created_at.label('request_time'),
            func.json_extract(MetricEvent.attributes, '$.url').label('url'),
            func.json_extract(MetricEvent.attributes, '$.endpoint').label('endpoint'),
            func.json_extract(MetricEvent.attributes, '$.path').label('path'),
            func.json_extract(MetricEvent.attributes, '$.method').label('method'),
            func.json_extract(MetricEvent.attributes, '$.request_id').label('request_identifier')
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'http_request')
        ).subquery()
        
        # Get response events
        responses = self.db.query(
            MetricEvent.session_id,
            MetricEvent.created_at.label('response_time'),
            func.json_extract(MetricEvent.attributes, '$.status_code').label('status_code'),
            func.json_extract(MetricEvent.attributes, '$.status').label('status'),
            func.json_extract(MetricEvent.attributes, '$.duration_ms').label('duration_ms'),
            func.json_extract(MetricEvent.attributes, '$.request_id').label('request_identifier')
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'http_response')
        ).subquery()
        
        # Pair requests with responses
        paired_events = self.db.query(
            requests.c.request_id,
            requests.c.endpoint,
            requests.c.path,
            requests.c.url,
            requests.c.method,
            responses.c.status_code,
            responses.c.status,
            responses.c.duration_ms,
            func.extract('epoch', responses.c.response_time - requests.c.request_time).label('duration_seconds')
        ).join(
            responses,
            and_(
                requests.c.session_id == responses.c.session_id,
                requests.c.request_time < responses.c.response_time,
                # Optional: match by request identifier if available
                func.coalesce(requests.c.request_identifier == responses.c.request_identifier, True)
            )
        ).all()
        
        if not paired_events:
            return self._get_empty_http_overview()
        
        # Process paired events
        durations = []
        error_count = 0
        endpoint_data = {}
        
        for event in paired_events:
            # Calculate duration (prefer duration_ms from attributes, then calculated difference)
            duration = None
            if event.duration_ms is not None:
                duration = float(event.duration_ms)
            elif event.duration_seconds is not None:
                duration = event.duration_seconds * 1000  # Convert to ms
            
            if duration is not None:
                durations.append(duration)
            
            # Get status code
            status_code = event.status_code or event.status
            if status_code:
                try:
                    status_int = int(status_code)
                    if status_int >= 400:
                        error_count += 1
                except (ValueError, TypeError):
                    pass
            
            # Get endpoint
            endpoint = event.endpoint or event.path or event.url or 'unknown'
            method = event.method or 'GET'
            endpoint_key = f"{method} {endpoint}"
            
            if endpoint_key not in endpoint_data:
                endpoint_data[endpoint_key] = {
                    'count': 0,
                    'durations': [],
                    'errors': 0
                }
            
            endpoint_data[endpoint_key]['count'] += 1
            if duration is not None:
                endpoint_data[endpoint_key]['durations'].append(duration)
            if status_code and int(status_code) >= 400:
                endpoint_data[endpoint_key]['errors'] += 1
        
        # Calculate percentiles
        durations_sorted = sorted(durations)
        total_requests = len(durations)
        
        p95_index = int(len(durations_sorted) * 0.95)
        p99_index = int(len(durations_sorted) * 0.99)
        
        avg_response_time = sum(durations) / len(durations) if durations else 0
        p95_response_time = durations_sorted[p95_index] if p95_index < len(durations_sorted) else 0
        p99_response_time = durations_sorted[p99_index] if p99_index < len(durations_sorted) else 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        # Prepare endpoint performance
        endpoints = []
        for endpoint_key, data in endpoint_data.items():
            endpoint_durations = sorted(data['durations'])
            endpoint_p95_index = int(len(endpoint_durations) * 0.95)
            
            endpoints.append({
                'endpoint': endpoint_key,
                'request_count': data['count'],
                'avg_response_time_ms': round(sum(data['durations']) / len(data['durations']), 2) if data['durations'] else 0,
                'p95_response_time_ms': round(endpoint_durations[endpoint_p95_index], 2) if endpoint_p95_index < len(endpoint_durations) else 0,
                'error_rate_percent': round((data['errors'] / data['count'] * 100), 2) if data['count'] > 0 else 0
            })
        
        # Sort by request count and return top 10
        endpoints.sort(key=lambda x: x['request_count'], reverse=True)
        
        return {
            "total_requests": total_requests,
            "error_rate_percent": round(error_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "p95_response_time_ms": round(p95_response_time, 2),
            "p99_response_time_ms": round(p99_response_time, 2),
            "endpoints": endpoints[:10],
            "time_range_days": None
        }
    
    def _get_empty_http_overview(self) -> Dict[str, Any]:
        """Return empty HTTP overview structure"""
        return {
            "total_requests": 0,
            "error_rate_percent": 0.0,
            "avg_response_time_ms": 0.0,
            "p95_response_time_ms": 0.0,
            "p99_response_time_ms": 0.0,
            "endpoints": [],
            "time_range_days": None
        }
    
    def get_http_performance_by_endpoint(
        self,
        app_token_id: int,
        endpoint_filter: Optional[str] = None,
        time_range_days: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """
        Get detailed HTTP performance metrics for specific endpoints
        """
        
        base_filter = and_(
            MetricEvent.app_token_id == app_token_id,
            MetricEvent.event_type.in_(['http_request', 'http_response', 'http_performance'])
        )
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(base_filter, MetricEvent.created_at >= time_threshold)
        
        # Get performance data
        query = self.db.query(
            func.json_extract(MetricEvent.attributes, '$.endpoint').label('endpoint'),
            func.json_extract(MetricEvent.attributes, '$.path').label('path'),
            func.json_extract(MetricEvent.attributes, '$.url').label('url'),
            func.json_extract(MetricEvent.attributes, '$.method').label('method'),
            func.json_extract(MetricEvent.attributes, '$.duration_ms').label('duration_ms'),
            func.json_extract(MetricEvent.attributes, '$.response_time_ms').label('response_time_ms'),
            func.json_extract(MetricEvent.attributes, '$.status_code').label('status_code'),
            MetricEvent.value.label('value_duration')
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'http_performance')
        )
        
        if endpoint_filter:
            query = query.filter(
                or_(
                    func.json_extract(MetricEvent.attributes, '$.endpoint').like(f"%{endpoint_filter}%"),
                    func.json_extract(MetricEvent.attributes, '$.path').like(f"%{endpoint_filter}%"),
                    func.json_extract(MetricEvent.attributes, '$.url').like(f"%{endpoint_filter}%")
                )
            )
        
        results = query.all()
        
        if not results:
            return []
        
        endpoint_metrics = {}
        
        for row in results:
            endpoint = row.endpoint or row.path or row.url or 'unknown'
            method = row.method or 'GET'
            endpoint_key = f"{method} {endpoint}"
            
            duration = None
            if row.duration_ms is not None:
                duration = float(row.duration_ms)
            elif row.response_time_ms is not None:
                duration = float(row.response_time_ms)
            elif row.value_duration:
                try:
                    duration = float(row.value_duration)
                except (ValueError, TypeError):
                    pass
            
            status_code = row.status_code
            is_error = False
            if status_code:
                try:
                    if int(status_code) >= 400:
                        is_error = True
                except (ValueError, TypeError):
                    pass
            
            if endpoint_key not in endpoint_metrics:
                endpoint_metrics[endpoint_key] = {
                    'endpoint': endpoint_key,
                    'method': method,
                    'total_requests': 0,
                    'error_count': 0,
                    'durations': []
                }
            
            endpoint_metrics[endpoint_key]['total_requests'] += 1
            if is_error:
                endpoint_metrics[endpoint_key]['error_count'] += 1
            if duration is not None:
                endpoint_metrics[endpoint_key]['durations'].append(duration)
        
        # Calculate metrics for each endpoint
        result = []
        for endpoint_key, metrics in endpoint_metrics.items():
            durations_sorted = sorted(metrics['durations'])
            p95_index = int(len(durations_sorted) * 0.95)
            p99_index = int(len(durations_sorted) * 0.99)
            
            result.append({
                'endpoint': metrics['endpoint'],
                'method': metrics['method'],
                'total_requests': metrics['total_requests'],
                'error_rate_percent': round((metrics['error_count'] / metrics['total_requests'] * 100), 2),
                'avg_response_time_ms': round(sum(metrics['durations']) / len(metrics['durations']), 2) if metrics['durations'] else 0,
                'p95_response_time_ms': round(durations_sorted[p95_index], 2) if p95_index < len(durations_sorted) else 0,
                'p99_response_time_ms': round(durations_sorted[p99_index], 2) if p99_index < len(durations_sorted) else 0
            })
        
        # Sort by total requests
        result.sort(key=lambda x: x['total_requests'], reverse=True)
        
        return result
    
    def get_crash_timeline(
        self,
        app_token_id: int,
        time_range_days: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """
        Get crash events grouped by day for timeline visualization.
        
        Assumptions:
        - Crash events have event_type = 'crash'
        - Crash timestamp is stored in created_at field
        
        Returns:
            List of dicts with:
            - date: Date of the crashes (YYYY-MM-DD)
            - crash_count: Number of crashes on that date
        """
        
        # Base filter
        base_filter = and_(
            MetricEvent.app_token_id == app_token_id,
            MetricEvent.event_type == 'crash'
        )
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(base_filter, MetricEvent.created_at >= time_threshold)
        
        # Group by date (using date part only, ignoring time)
        crash_timeline = self.db.query(
            func.date(MetricEvent.created_at).label('date'),
            func.count(MetricEvent.id).label('crash_count')
        ).filter(base_filter).group_by(
            func.date(MetricEvent.created_at)
        ).order_by(
            func.date(MetricEvent.created_at)
        ).all()
        
        # Fill in missing dates with zero crashes
        if time_range_days and crash_timeline:
            result = self._fill_missing_dates(crash_timeline, time_range_days)
        else:
            result = [
                {
                    "date": row.date,
                    "crash_count": row.crash_count
                }
                for row in crash_timeline
            ]
        
        return result
    
    def _fill_missing_dates(
        self,
        crash_timeline,
        time_range_days: int
    ) -> List[Dict[str, Any]]:
        """Fill in dates with zero crashes for complete timeline"""
        
        # Generate all dates in the range
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=time_range_days - 1)
        
        # Create a dict of existing crash counts
        crash_dict = {row.date: row.crash_count for row in crash_timeline}
        
        # Fill all dates
        result = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            result.append({
                "date": date_str,
                "crash_count": crash_dict.get(date_str, 0)
            })
            current_date += timedelta(days=1)
        
        return result
    
    def get_crash_summary(
        self,
        app_token_id: int,
        time_range_days: Optional[int] = 30
    ) -> Dict[str, Any]:
        """
        Get crash summary statistics including total crashes and crash-free sessions.
        """
        
        base_filter = and_(
            MetricEvent.app_token_id == app_token_id
        )
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(base_filter, MetricEvent.created_at >= time_threshold)
        
        # Total crashes
        total_crashes = self.db.query(
            func.count(MetricEvent.id)
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'crash')
        ).scalar() or 0
        
        # Total sessions (unique session_id)
        total_sessions = self.db.query(
            func.count(func.distinct(MetricEvent.session_id))
        ).filter(base_filter).scalar() or 0
        
        # Crash-free sessions (sessions with no crash events)
        sessions_with_crashes = self.db.query(
            func.count(func.distinct(MetricEvent.session_id))
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'crash')
        ).scalar() or 0
        
        crash_free_sessions = total_sessions - sessions_with_crashes
        
        # Crash rate per session
        crash_rate_per_session = (total_crashes / total_sessions * 100) if total_sessions > 0 else 0
        
        return {
            "total_crashes": total_crashes,
            "total_sessions": total_sessions,
            "crash_free_sessions": crash_free_sessions,
            "crash_rate_per_session_percent": round(crash_rate_per_session, 2),
            "time_range_days": time_range_days
        }
    
    def get_crash_details_by_date(
        self,
        app_token_id: int,
        target_date: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get detailed crash information for a specific date.
        """
        
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        crashes = self.db.query(MetricEvent).filter(
            and_(
                MetricEvent.app_token_id == app_token_id,
                MetricEvent.event_type == 'crash',
                MetricEvent.created_at >= start_of_day,
                MetricEvent.created_at < end_of_day
            )
        ).order_by(
            MetricEvent.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "session_id": crash.session_id,
                "device_id": crash.device_id,
                "timestamp": crash.created_at.isoformat() if crash.created_at else None,
                "crash_reason": crash.attributes.get('reason') if crash.attributes else None,
                "crash_stack": crash.attributes.get('stack_trace') if crash.attributes else None,
                "os_version": crash.attributes.get('os_version') if crash.attributes else None,
                "app_version": crash.attributes.get('app_version') if crash.attributes else None
            }
            for crash in crashes
        ]
    
    def get_device_breakdown(
        self,
        app_token_id: int,
        limit: int = 20,
        offset: int = 0,
        time_range_days: Optional[int] = 30,
        sort_by: str = "sessions",
        sort_order: str = "desc"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get breakdown by device_id with sessions, crashes, and avg memory.
        
        Args:
            app_token_id: App token ID
            limit: Number of devices to return
            offset: Number of devices to skip (for pagination)
            time_range_days: Time range in days (None for all time)
            sort_by: Field to sort by (sessions, crashes, avg_memory_mb, device_id)
            sort_order: Sort order (asc or desc)
        
        Returns:
            Tuple of (list of device metrics, total number of unique devices)
        """
        
        # Base filter for time range
        base_filter = MetricEvent.app_token_id == app_token_id
        
        if time_range_days:
            time_threshold = datetime.utcnow() - timedelta(days=time_range_days)
            base_filter = and_(base_filter, MetricEvent.created_at >= time_threshold)
        
        # Subquery for sessions per device (unique session_id)
        sessions_per_device = self.db.query(
            MetricEvent.device_id,
            func.count(func.distinct(MetricEvent.session_id)).label('session_count')
        ).filter(base_filter).group_by(MetricEvent.device_id).subquery()
        
        # Subquery for crashes per device
        crashes_per_device = self.db.query(
            MetricEvent.device_id,
            func.count(MetricEvent.id).label('crash_count')
        ).filter(
            and_(base_filter, MetricEvent.event_type == 'crash')
        ).group_by(MetricEvent.device_id).subquery()
        
        # Subquery for average memory usage (assuming memory in attributes.memory_mb)
        memory_per_device = self.db.query(
            MetricEvent.device_id,
            func.avg(
                func.json_extract(MetricEvent.attributes, '$.memory_mb')
            ).label('avg_memory_mb')
        ).filter(
            and_(
                base_filter,
                func.json_extract(MetricEvent.attributes, '$.memory_mb').isnot(None)
            )
        ).group_by(MetricEvent.device_id).subquery()
        
        # Main query combining all metrics
        query = self.db.query(
            MetricEvent.device_id,
            func.coalesce(sessions_per_device.c.session_count, 0).label('sessions'),
            func.coalesce(crashes_per_device.c.crash_count, 0).label('crashes'),
            func.coalesce(memory_per_device.c.avg_memory_mb, 0).label('avg_memory_mb')
        ).outerjoin(
            sessions_per_device,
            MetricEvent.device_id == sessions_per_device.c.device_id
        ).outerjoin(
            crashes_per_device,
            MetricEvent.device_id == crashes_per_device.c.device_id
        ).outerjoin(
            memory_per_device,
            MetricEvent.device_id == memory_per_device.c.device_id
        ).filter(base_filter).group_by(MetricEvent.device_id)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply sorting
        if sort_by == "sessions":
            order_col = func.coalesce(sessions_per_device.c.session_count, 0)
        elif sort_by == "crashes":
            order_col = func.coalesce(crashes_per_device.c.crash_count, 0)
        elif sort_by == "avg_memory_mb":
            order_col = func.coalesce(memory_per_device.c.avg_memory_mb, 0)
        elif sort_by == "device_id":
            order_col = MetricEvent.device_id
        else:
            order_col = func.coalesce(sessions_per_device.c.session_count, 0)
        
        if sort_order.lower() == "desc":
            query = query.order_by(desc(order_col))
        else:
            query = query.order_by(order_col)
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query
        results = query.all()
        
        # Format results
        devices = [
            {
                "device_id": row.device_id,
                "sessions": row.sessions,
                "crashes": row.crashes,
                "avg_memory_mb": round(row.avg_memory_mb, 2) if row.avg_memory_mb else 0
            }
            for row in results
        ]
        
        return devices, total_count
    
