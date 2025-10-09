import bcrypt
from sqlalchemy import text
from flask import request, flash, redirect, url_for, session, render_template
from .projects import get_projects_for_user, get_projects_for_student

def register_user(request, engine, is_debug=False):
    email = request.form.get('email')
    password = request.form.get('password')
    password2 = request.form.get('password2')
    role = request.form.get('role')

    permission = 0

    if role == '1':
        permission = 1

    if not all([email, password, password2, role]):
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
                    "INSERT INTO users (email, password, role, permission) VALUES (:email, :password, :role, :permission)"
                )
                params = {
                    "email": email,
                    "password": db_password,
                    "role": int(role),
                    "permission": int(permission)
                }
                connection.execute(insert_query, params)
                connection.commit()
                
                flash(f"Account for {email} created successfully! You can now log in.", "success")
                return redirect(url_for('login'))

    except Exception as e:
        print(f"Database error during registration: {e}")
        flash("An error occurred during registration. Please try again later.", "danger")
    
    return redirect(url_for('register'))


def login_user(request, engine, is_debug=False):
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
            query = text("SELECT id, email, password, role, permission FROM users WHERE email = :email")
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
                    session['role'] = result.role
                    session['permission'] = result.permission
                    flash(f"Welcome back, {email}!", "success")
                    return redirect(url_for('profile'))
            
            flash("Invalid email or password. Please try again.", "danger")

    except Exception as e:
        print(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again later.", "danger")

    return redirect(url_for('login'))

def get_profile_data(engine):
    if session['role'] == 3:
        student_id = session['user_id']
        with engine.connect() as conn:
            student_query = text("""
                SELECT s.instructor_id, i.email AS instructor_email
                FROM users s LEFT JOIN users i ON s.instructor_id = i.id
                WHERE s.id = :student_id
            """)
            student_info = conn.execute(student_query, {"student_id": student_id}).first()

            pending_request = None
            instructors = []
            
            if not student_info.instructor_id:
                req_query = text("""
                    SELECT r.id, u.email AS instructor_email
                    FROM instructor_requests r JOIN users u ON r.instructor_id = u.id
                    WHERE r.student_id = :student_id AND r.status = 0
                """)
                pending_request = conn.execute(req_query, {"student_id": student_id}).first()

                if not pending_request:
                    inst_query = text("SELECT id, email FROM users WHERE role = 0 ORDER BY email")
                    instructors = conn.execute(inst_query).all()

            assignments = get_projects_for_student(engine)
            return render_template('profile.html', 
                                   assignments=assignments, 
                                   student_info=student_info,
                                   instructors=instructors,
                                   pending_request=pending_request)
    else:
        projects = get_projects_for_user(engine)
        return render_template('profile.html', projects=projects)

def get_business_profile_data(user_id, engine):
    try:
        with engine.connect() as conn:
            user_query = text("""
                SELECT id, name, email, bio
                FROM users
                WHERE id = :user_id AND role = 1
            """)
            business_user = conn.execute(user_query, {"user_id": user_id}).mappings().first()

            if not business_user:
                flash("Business profile not found.", "warning")
                return None

            projects_query = text("""
                SELECT id, name, description, status
                FROM projects
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """)
            projects = conn.execute(projects_query, {"user_id": user_id}).mappings().all()

            return render_template(
                'business_profile.html',
                business_user=business_user,
                projects=projects
            )
    except Exception as e:
        print(f"Error fetching business profile data: {e}")
        flash("An error occurred while trying to load the profile.", "danger")
        return None
