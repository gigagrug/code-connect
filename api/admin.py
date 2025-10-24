import bcrypt
from sqlalchemy import text
from flask import request, flash, redirect, url_for, session, render_template, jsonify
from .projects import get_projects_for_user, get_projects_for_student

def register_admin(request, engine, is_debug=False):
    email = request.form.get('email')
    password = request.form.get('password')
    password2 = request.form.get('password2')
    account_type = request.form.get('account_type')

    role = 0

    if account_type == '1':
        role = 1

    if not all([email, password, password2, account_type]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('register'))

    if password != password2:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('register'))

    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(url_for('register'))

    try:
        db_password = ""
        if is_debug:
            db_password = password
        else:
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
                    "INSERT INTO users (email, password, account_type, role) VALUES (:email, :password, :account_type, :role)"
                )
                params = {
                    "email": email,
                    "password": db_password,
                    "account_type": 10,
                    "role": int(role)
                }
                connection.execute(insert_query, params)
                connection.commit()
                
                flash(f"Account for {email} created successfully! You can now log in.", "success")
                return redirect(url_for('login'))

    except Exception as e:
        print(f"Database error during registration: {e}")
        flash("An error occurred during registration. Please try again later.", "danger")
    
    return redirect(url_for('register'))


def login_admin(request, engine, is_debug=False):
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect(url_for('login'))

    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(url_for('login'))

    try:
        with engine.connect() as connection:
            query = text("SELECT id, email, password, account_type, role FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email}).mappings().first()

            if result:
                password_matches = False
                if is_debug:
                    password_matches = (result.password == password)
                else:
                    hashed_password_from_db = result.password.encode('utf-8')
                    submitted_password_bytes = password.encode('utf-8')
                    password_matches = bcrypt.checkpw(submitted_password_bytes, hashed_password_from_db)

                if password_matches:
                    session.clear()
                    session['user_id'] = result.id
                    session['email'] = result.email
                    session['account_type'] = result.account_type
                    session['role'] = result.role
                    flash(f"Welcome back, {email}!", "success")
                    return redirect(url_for('profile'))
            
            flash("Invalid email or password. Please try again.", "danger")

    except Exception as e:
        print(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again later.", "danger")

    return redirect(url_for('login'))

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
