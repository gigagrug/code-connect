from sqlalchemy import text
from flask import flash, redirect, url_for, session, request, jsonify

def get_projects_paginated(engine, page: int = 1, per_page: int = 5):
    page = max(page, 1)
    offset = (page - 1) * per_page
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM projects")).scalar()
        rows = conn.execute(text("""
            SELECT *
            FROM projects
            ORDER BY created_at DESC, id DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": per_page, "offset": offset}).mappings().all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, total_pages