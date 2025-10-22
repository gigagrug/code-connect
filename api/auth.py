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
    user_role = session.get('role')
    user_id = session.get('user_id')

    if user_role == 3: # Student Logic
        with engine.connect() as conn:
            student_query = text("""
                SELECT s.instructor_id, i.email AS instructor_email
                FROM users s LEFT JOIN users i ON s.instructor_id = i.id
                WHERE s.id = :student_id
            """)
            student_info = conn.execute(student_query, {"student_id": user_id}).first()

            pending_request = None
            instructors = []
            
            if not student_info.instructor_id:
                req_query = text("""
                    SELECT r.id, u.email AS instructor_email
                    FROM instructor_requests r JOIN users u ON r.instructor_id = u.id
                    WHERE r.student_id = :student_id AND r.status = 0
                """)
                pending_request = conn.execute(req_query, {"student_id": user_id}).first()

                if not pending_request:
                    inst_query = text("SELECT id, email FROM users WHERE role = 0 ORDER BY email")
                    instructors = conn.execute(inst_query).all()

            assignments = get_projects_for_student(engine)
            return render_template('profile.html', 
                                   assignments=assignments, 
                                   student_info=student_info,
                                   instructors=instructors,
                                   pending_request=pending_request)

    elif user_role == 0: # Instructor Logic
        with engine.connect() as conn:
            # New query to get projects managed by the instructor
            approved_projects_query = text("""
                SELECT p.id, p.name, p.description, p.status
                FROM instructor_projects ip
                JOIN projects p ON ip.project_id = p.id
                WHERE ip.instructor_id = :instructor_id
                ORDER BY p.id DESC
            """)
            approved_projects = conn.execute(
                approved_projects_query, 
                {"instructor_id": user_id}
            ).mappings().all()

        # Also get projects created by the instructor
        created_projects = get_projects_for_user(engine)
        
        return render_template(
            'profile.html',
            approved_projects=approved_projects,
            created_projects=created_projects
        )

    else: # Logic for other roles (e.g., Business)
        projects = get_projects_for_user(engine)
        return render_template('profile.html', projects=projects)

def get_business_profile_data(user_id, engine):
    try:
        with engine.connect() as conn:
            user_query = text("""
                SELECT id, name, bio
                FROM users
                WHERE id = :user_id AND role = 1
            """)
            business_user = conn.execute(user_query, {"user_id": user_id}).mappings().first()

            if not business_user:
                flash("Business profile not found.", "warning")
                return None

            projects_query = text("""
                SELECT p.id, p.name, p.description, p.status, u.name
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE p.user_id = :user_id
                ORDER BY p.created_at DESC
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

def update_profile(engine):
    """Handles updating user profile information."""
    if 'user_id' not in session:
        flash("You must be logged in to update your profile.", "danger")
        return redirect('/login')

    user_id = session.get('user_id')
    user_role = session.get('role')
    
    name = request.form.get('name', '').strip()

    try:
        with engine.connect() as conn:
            with conn.begin():  # Start a transaction
                # Update name for the current user
                query_name = text("UPDATE users SET name = :name WHERE id = :user_id")
                conn.execute(query_name, {"name": name, "user_id": user_id})

                # Role-specific updates
                if user_role == 1:  # Business User can also update bio
                    bio = request.form.get('bio', '').strip()
                    query_bio = text("UPDATE users SET bio = :bio WHERE id = :user_id")
                    conn.execute(query_bio, {"bio": bio, "user_id": user_id})

                elif user_role == 3:  # Student can also update graduation year
                    graduation = request.form.get('graduation', '').strip()
                    query_grad = text("UPDATE users SET graduation = :graduation WHERE id = :user_id")
                    conn.execute(query_grad, {"graduation": graduation, "user_id": user_id})

            flash("Profile updated successfully!", "success")
    except Exception as e:
        print(f"Error updating profile: {e}")
        flash("An error occurred while updating your profile.", "danger")

    return redirect('/profile')

def get_profile_data(engine):
    user_role = session.get('role')
    user_id = session.get('user_id')

    # Fetch base user data for everyone
    with engine.connect() as conn:
        user_data_query = text("SELECT name, bio FROM users WHERE id = :user_id")
        user_data = conn.execute(user_data_query, {"user_id": user_id}).mappings().first()

    if user_role == 3: # Student Logic
        with engine.connect() as conn:
            student_query = text("""
                SELECT s.instructor_id, i.name AS instructor_email, s.graduation
                FROM users s LEFT JOIN users i ON s.instructor_id = i.id
                WHERE s.id = :student_id
            """)
            student_info = conn.execute(student_query, {"student_id": user_id}).first()

            pending_request = None
            instructors = []
            
            if not student_info.instructor_id:
                req_query = text("""
                    SELECT r.id, u.email AS instructor_email
                    FROM instructor_requests r JOIN users u ON r.instructor_id = u.id
                    WHERE r.student_id = :student_id AND r.status = 0
                """)
                pending_request = conn.execute(req_query, {"student_id": user_id}).first()

                if not pending_request:
                    inst_query = text("SELECT id, email FROM users WHERE role = 0 ORDER BY email")
                    instructors = conn.execute(inst_query).all()

        assignments = get_projects_for_student(engine)
        return render_template('profile.html', 
                               assignments=assignments, 
                               student_info=student_info,
                               instructors=instructors,
                               pending_request=pending_request,
                               user_data=user_data) # Pass user_data as well

    elif user_role == 0: # Instructor Logic
        with engine.connect() as conn:
            approved_projects_query = text("""
                SELECT p.id, p.name, p.description, p.status, u.name
                FROM instructor_projects ip
                JOIN projects p ON ip.project_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE ip.instructor_id = :instructor_id
                ORDER BY p.id DESC
            """)
            approved_projects = conn.execute(
                approved_projects_query, 
                {"instructor_id": user_id}
            ).mappings().all()
        created_projects = get_projects_for_user(engine)
        return render_template(
            'profile.html',
            approved_projects=approved_projects,
            created_projects=created_projects,
            user_data=user_data
        )

    else: # Logic for Business and other roles
        projects = get_projects_for_user(engine)
        return render_template('profile.html', projects=projects, user_data=user_data)

def create_admin_message(request, engine):
    """Saves a new message from a user to the admin."""
    if 'user_id' not in session:
        flash("You must be logged in to send a message.", "warning")
        return redirect(url_for('login'))

    message = request.form.get('message')
    if not message or not message.strip():
        flash("Message cannot be empty.", "danger")
        return redirect(url_or('profile'))

    user_id = session['user_id']
    
    try:
        with engine.connect() as conn:
            query = text("INSERT INTO admin_messages (user_id, message) VALUES (:user_id, :message)")
            conn.execute(query, {"user_id": user_id, "message": message.strip()})
            conn.commit()
        flash("Your message has been sent to the administrators.", "success")
    except Exception as e:
        print(f"Error saving admin message: {e}")
        flash("An error occurred while sending your message.", "danger")

    return redirect(url_for('profile'))
