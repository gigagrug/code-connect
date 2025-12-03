from sqlalchemy import text

# a page with every single job in the database and their relevant information

def get_jobs_paginated(engine, page: int = 1, per_page: int = 6, q: str | None = None, status: str | None = None):
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 1), 1)
    offset = (page - 1) * per_page

    where = []
    params = {}

    if q:
        where.append("(title LIKE :q OR description LIKE :q)")
        params["q"] = f"%{q}%"

    if status is not None and status != "":
        where.append("status = :status")
        params["status"] = status

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM jobs {where_sql}"), params).scalar() or 0

        # Global status counts (not affected by filters)
        # determines the status of a job
        counts = conn.execute(text(
            """
            SELECT 
              SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS pending_count,
              SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS approved_count,
              SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS taken_count
            FROM jobs
            """
        )).mappings().first() or {"pending_count": 0, "approved_count": 0, "taken_count": 0}

        rows = conn.execute(
            text(f"""
                SELECT *
                FROM jobs
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


def admin_update_job_status(engine, job_id: int, status: int) -> bool:
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE jobs SET status = :status WHERE id = :job_id"),
                {"status": int(status), "job_id": int(job_id)},
            )
            conn.commit()
        return True
    except Exception:
        return False


def admin_delete_job(engine, job_id: int) -> bool:
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM jobs WHERE id = :job_id"), {"job_id": int(job_id)})
            conn.commit()
        return True
    except Exception:
        return False
