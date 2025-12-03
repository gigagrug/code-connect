from sqlalchemy import text

def get_jobs_paginated(engine, page: int = 1, per_page: int = 6, q: str | None = None, role: str | None = None):
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 1), 1)
    offset = (page - 1) * per_page

    where = []
    params = {}

    if q:
        where.append("(title LIKE :q OR description LIKE :q)")
        params["q"] = f"%{q}%"

    if role is not None and role != "":
        where.append("role = :role")
        params["role"] = role

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM users {where_sql}"), params).scalar() or 0

        # Global role counts (not affected by filters)
        # Determines the status of a Job
        counts = conn.execute(text(
            """
            SELECT 
              SUM(CASE WHEN role = 0 THEN 1 ELSE 0 END) AS pending_count,
              SUM(CASE WHEN role = 1 THEN 1 ELSE 0 END) AS approved_count,
              SUM(CASE WHEN role = 2 THEN 1 ELSE 0 END) AS taken_count
            FROM jobs
            """
        )).mappings().first() or {"pending_count": 0, "approved_count": 0, "taken_count": 0}

        rows = conn.execute(
            text(f"""
                SELECT *
                FROM users
                {where_sql}
                ORDER BY id ASC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": per_page, "offset": offset},
        ).mappings().all()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return (
        rows,
        total,
        total_pages,
        counts.get("pending_count", 0),
        counts.get("approved_count", 0),
        counts.get("taken_count", 0),
    )
