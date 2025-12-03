from sqlalchemy import text

# a page with a table of all support messages and their information

def get_admin_messages(engine):
    """Return all admin messages ordered by newest first."""
    if engine is None:
        return []
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
