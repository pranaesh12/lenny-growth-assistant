"""
Top-level API router.

This module aggregates all versioned API routers (v1, and future v2+)
into a single router that gets included into the FastAPI app in
`app/main.py`. This is the ONLY place version prefixes are composed
at the top level — individual version routers do not know about
each other.
"""

from fastapi import APIRouter

from app.api.v1.router import api_v1_router

api_router = APIRouter()

# --- Version 1 ---
api_router.include_router(api_v1_router)

# --- Future versions are added here, e.g.: ---
# from app.api.v2.router import api_v2_router
# api_router.include_router(api_v2_router)