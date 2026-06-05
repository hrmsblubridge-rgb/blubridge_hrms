"""
Operational Vigilance Report — additive module.

Self-contained package mounted onto the main FastAPI app via a factory
(`get_vigilance_router`) so there is NO import cycle with server.py and ZERO
modification to existing HRMS modules (attendance / payroll / leave / employee).

Attendance remains the single source of truth: system columns (Punch-In/Out,
Total Hours, Name/Email/Team) are resolved LIVE and never mutated here.
"""
from .router import get_vigilance_router, ensure_vigilance_indexes

__all__ = ["get_vigilance_router", "ensure_vigilance_indexes"]
