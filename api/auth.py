import bcrypt
from sqlalchemy import text
from flask import flash, redirect, url_for, session

def register_user(request, engine):
    email = request.form.get('email')
    password = request.form.get('password')
    password2 = request.form.get('password2')
    account_type = request.form.get('account_type')

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
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        with engine.connect() as connection:
            query = text("SELECT email FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email}).fetchone()

            if result:
                flash('An account with this email already exists.', 'warning')
            else:
                insert_query = text(
                    "INSERT INTO users (email, password, account_type) VALUES (:email, :password, :account_type)"
                )
                params = {
                    "email": email,
                    "password": hashed_password,
                    "account_type": int(account_type)
                }
                connection.execute(insert_query, params)
                connection.commit()
                
                flash(f"Account for {email} created successfully! You can now log in.", "success")
                return redirect(url_for('login'))

    except Exception as e:
        print(f"Database error during registration: {e}")
        flash("An error occurred during registration. Please try again later.", "danger")
    
    return redirect(url_for('register'))


def login_user(request, engine):
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
            query = text("SELECT email, password, account_type FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email}).fetchone()

            if result:
                hashed_password_from_db = result.password.encode('utf-8')
                submitted_password_bytes = password.encode('utf-8')
                
                if bcrypt.checkpw(submitted_password_bytes, hashed_password_from_db):
                    session['email'] = result.email
                    session['account_type'] = result.account_type
                    flash(f"Welcome back, {email}!", "success")
                    return redirect(url_for('profile'))
            
            flash("Invalid email or password. Please try again.", "danger")

    except Exception as e:
        print(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again later.", "danger")

    return redirect(url_for('login'))

def get_all_projects(engine):
    """Fetches all projects from all users to display publicly."""
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT p.name, p.description, u.email 
                FROM projects p
                JOIN users u ON p.user = u.id
                ORDER BY p.id DESC
            """)
            projects = connection.execute(query).fetchall()
            return projects
    except Exception as e:
        print(f"Database error fetching all projects: {e}")
        return []

_posts = [
    {"id": 1, "title": "First Post", "content": "This is the first post."},
    {"id": 2, "title": "Second Post", "content": "This is the second post."},
    {"id": 3, "title": "3 Post", "content": "This is the 3 post."},
    {"id": 4, "title": "4 Post", "content": "This is the 3 post."},
]

def get_all_posts():
    return _posts

def get_post_by_id(post_id):
    for post in _posts:
        if post["id"] == post_id:
            return post
    return None
