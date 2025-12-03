import bcrypt
from sqlalchemy import text
from flask import flash, redirect, url_for, session

# the login and registration page for administrators

def register_admin(request, engine):
    email = request.form.get('email')
    password = request.form.get('password')
    password2 = request.form.get('password2')

    if not all([email, password, password2]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('register'))

    if password != password2:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('register'))

    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(url_for('admin_register'))

    try:
        db_password = ""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        db_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        with engine.connect() as connection:
            query = text("SELECT email FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email}).fetchone()

            if result:
                flash('An account with this email already exists.', 'warning')
            else:
                insert_query = text(
                    "INSERT INTO users (email, password, role, permission) VALUES (:email, :password, :role, :permission)"
                )
                params = {
                    "email": email,
                    "password": db_password,
                    "role": 10,
                    "permission": 10 
                }
                connection.execute(insert_query, params)
                connection.commit()
                
                flash(f"Account for {email} created successfully! You can now log in.", "success")
                return redirect(url_for('admin_login'))

    except Exception as e:
        print(f"Database error during registration: {e}")
        flash("An error occurred during registration. Please try again later.", "danger")
    
    return redirect(url_for('admin_register'))


def login_admin(request, engine):
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect(url_for('admin_login'))

    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(url_for('admin_login'))

    try:
        with engine.connect() as connection:
            query = text("SELECT id, email, password, role, permission FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email}).mappings().first()

            if result:
                password_matches = False
                hashed_password_from_db = result.password.encode('utf-8')
                submitted_password_bytes = password.encode('utf-8')
                password_matches = bcrypt.checkpw(submitted_password_bytes, hashed_password_from_db)

                if password_matches:
                    session.clear()
                    session['user_id'] = result.id
                    session['email'] = result.email
                    session['role'] = result.role
                    session['permission'] = result.permission
                    flash(f"Welcome back, {email}!", "success")
                    return redirect(url_for('admin_index'))
            
            flash("Invalid email or password. Please try again.", "danger")

    except Exception as e:
        print(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again later.", "danger")

    return redirect(url_for('admin_login'))

def get_projects_paginated(engine, page: int = 1, per_page: int = 6, q: str | None = None, status: str | None = None):
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 1), 1)
    offset = (page - 1) * per_page

    where = []
    params = {}

    if q:
        where.append("(name LIKE :q OR description LIKE :q)")
        params["q"] = f"%{q}%"

    if status:
        where.append("status = :status")
        params["status"] = status

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM projects {where_sql}"), params).scalar() or 0

        counts = conn.execute(text(
            """
            SELECT 
              SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS pending_count,
              SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS approved_count,
              SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS taken_count
            FROM projects
            """
        )).mappings().first() or {"pending_count": 0, "approved_count": 0, "taken_count": 0}

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
        except Exception as e:
            print(f"Error fetching projects: {e}")
            rows = []

    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, total_pages, counts.get("pending_count", 0), counts.get("approved_count", 0), counts.get("taken_count", 0)

def get_users_paginated(engine, page: int = 1, per_page: int = 6, q: str | None = None, status: str | None = None):
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
        total = conn.execute(text(f"SELECT COUNT(*) FROM users {where_sql}"), params).scalar() or 0

        counts = conn.execute(text(
            """
            SELECT 
              SUM(CASE WHEN role = 0 THEN 1 ELSE 0 END) AS pending_count,
              SUM(CASE WHEN role = 1 THEN 1 ELSE 0 END) AS approved_count,
              SUM(CASE WHEN role = 2 THEN 1 ELSE 0 END) AS taken_count
            FROM users
            """
        )).mappings().first() or {"pending_count": 0, "approved_count": 0, "taken_count": 0}

        try:
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
        except Exception:
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
    return rows, total, total_pages, counts.get("pending_count", 0), counts.get("approved_count", 0), counts.get("taken_count", 0)
