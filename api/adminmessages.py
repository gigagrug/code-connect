from sqlalchemy import text

def get_admin_messages(engine):
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, user_id, message, timestamp
                    FROM admin_messages
                    ORDER BY timestamp DESC, id DESC
                    """
                )
            ).mappings().all()
        return rows
    except Exception:
        return []
