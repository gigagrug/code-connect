from sqlalchemy import text

def get_projects_paginated(engine, page: int = 1, per_page: int = 6, q: str | None = None, status: str | None = None):
    """
    Returns (rows, total, total_pages, pending_count, approved_count, taken_count).
    - q: optional substring match on title/description (legacy names title/description)
    - status: optional exact status filter value (0=pending, 1=approved, 2=taken)
    """
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 1), 1)
    offset = (page - 1) * per_page

    where = []
    params = {}

    if q:
        where.append("(title LIKE :q OR description LIKE :q)")
        params["q"] = f"%{q}%"

    if status:
        where.append("status = :status")
        params["status"] = status

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM projects {where_sql}"), params).scalar() or 0

        # Global status counts (not affected by filters)
        counts = conn.execute(text(
            """
            SELECT 
              SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS pending_count,
              SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS approved_count,
              SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS taken_count
            FROM projects
            """
        )).mappings().first() or {"pending_count": 0, "approved_count": 0, "taken_count": 0}

        # Order by ID ascending for deterministic paging
        try:
            rows = conn.execute(
                text(f"""
                    SELECT *
                    FROM projects
                    {where_sql}
                    ORDER BY id ASC
                    LIMIT :limit OFFSET :offset
                """),
                {**params, "limit": per_page, "offset": offset},
            ).mappings().all()
        except Exception:
            rows = conn.execute(
                text(f"""
                    SELECT *
                    FROM projects
                    {where_sql}
                    ORDER BY id ASC
                    LIMIT :limit OFFSET :offset
                """),
                {**params, "limit": per_page, "offset": offset},
            ).mappings().all()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, total_pages, counts.get("pending_count", 0), counts.get("approved_count", 0), counts.get("taken_count", 0)
