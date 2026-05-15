# Add to app/schemas/metric_event.py

from pydantic import BaseModel
from typing import Dict, Optional, List


class StatusCodeBreakdown(BaseModel):
    status_code: int
    count: int


class SlowestEndpoint(BaseModel):
    endpoint: str
    avg_latency_ms: float
    total_requests: int
    error_rate: float


class HttpPerformanceResponse(BaseModel):
    total_requests: int
    error_rate: float
    error_count: int
    avg_latency_ms: float
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_requests_per_minute: float
    status_code_breakdown: Dict[int, int]
    slowest_endpoints: List[SlowestEndpoint]
    success_rate: float
    performance_grade: Optional[str] = None
    date_range: Optional[Dict[str, Optional[str]]] = None
    
    class Config:
        from_attributes = True