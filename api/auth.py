import bcrypt
from sqlalchemy import text
from flask import request, flash, redirect, url_for, session, render_template
from .projects import get_projects_for_user, get_projects_for_student
from .job import get_my_applications
import os
import resend
import secrets
from datetime import datetime, timedelta

RESEND_KEY = os.environ.get('RESEND_KEY')
RESEND_EMAIL = os.environ.get('RESEND_EMAIL') 

def register_user(request, engine):
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
        db_password = password
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
                    return redirect(url_for('index'))
                
            flash("Invalid email or password. Please try again.", "danger")

    except Exception as e:
        print(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again later.", "danger")

    return redirect(url_for('login'))

def handle_forgot_password(request, engine):
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("Email address is required.", "danger")
            return redirect(url_for('forgot_password'))

        if not RESEND_KEY:
            print("RESEND_KEY environment variable not set. Cannot send password reset email.")
            flash("Email service is not configured. Please contact support.", "danger")
            return redirect(url_for('forgot_password'))

        try:
            with engine.connect() as conn:
                with conn.begin():
                    # Find user by email
                    user_query = text("SELECT id FROM users WHERE email = :email")
                    user = conn.execute(user_query, {"email": email}).mappings().first()

                    if user:
                        # 1. Generate a secure token
                        token = secrets.token_urlsafe(32)
                        expires_at = datetime.utcnow() + timedelta(hours=1) # Token valid for 1 hour
                        user_id = user.id

                        # 2. Store the token in the database (still inside transaction)
                        # Invalidate any old tokens for this user
                        delete_old_tokens = text("DELETE FROM password_reset_tokens WHERE user_id = :user_id")
                        conn.execute(delete_old_tokens, {"user_id": user_id})
                        
                        # Insert the new token
                        insert_token = text("""
                            INSERT INTO password_reset_tokens (user_id, token, expires_at)
                            VALUES (:user_id, :token, :expires_at)
                        """)
                        conn.execute(insert_token, {"user_id": user_id, "token": token, "expires_at": expires_at})

                        # 3. Create the reset link
                        reset_url = url_for('reset_password', token=token, _external=True)

                        # 4. Send the email (STILL inside transaction)
                        html_content = f"""
                        <p>Hello,</p>
                        <p>You requested a password reset for your account. Click the link below to set a new password:</p>
                        <p><a href="{reset_url}">{reset_url}</a></p>
                        <p>This link will expire in 1 hour.</p>
                        <p>If you did not request this, please ignore this email.</p>
                        """
                        
                        try:
                            resend.api_key = RESEND_KEY
                            r = resend.Emails.send({
                                "from": RESEND_EMAIL,
                                "to": email,
                                "subject": "Your Password Reset Request",
                                "html": html_content
                            })
                        
                        except Exception as e:
                            print(f"Error sending email via Resend: {e}")
                            flash("Could not send password reset email. Please try again later.", "danger")
                            return redirect(url_for('forgot_password'))

            flash("If an account with that email exists, a password reset link has been sent.", "info")
            return redirect(url_for('login'))

        except Exception as e:
            print(f"Database error during password reset request: {e}")
            flash("An error occurred. Please try again later.", "danger")
            return redirect(url_for('forgot_password'))
    return render_template('forgot_password.html')


def handle_reset_password(request, engine, token):
    try:
        with engine.connect() as conn:
            
            query = text("""
                SELECT user_id, expires_at FROM password_reset_tokens
                WHERE token = :token
            """)
            token_data = conn.execute(query, {"token": token}).mappings().first()

            if not token_data:
                flash("Invalid password reset link.", "danger")
                conn.rollback() # Rollback the autobegin transaction
                return redirect(url_for('login'))

            if datetime.utcnow() > token_data.expires_at:
                flash("Your password reset link has expired. Please request a new one.", "danger")
                
                # We are already in a transaction. Just execute and commit.
                delete_query = text("DELETE FROM password_reset_tokens WHERE token = :token")
                conn.execute(delete_query, {"token": token})
                conn.commit() # Commit the token deletion
                
                return redirect(url_for('login'))
            
            user_id = token_data.user_id

            # If it's a POST request, handle the form submission
            if request.method == 'POST':
                password = request.form.get('password')
                password2 = request.form.get('password2')

                if not password or not password2:
                    flash("Both password fields are required.", "danger")
                    conn.rollback() # Rollback the autobegin transaction
                    return render_template('reset_password.html', token=token) # Re-render form

                if password != password2:
                    flash("Passwords do not match.", "danger")
                    conn.rollback() # Rollback the autobegin transaction
                    return render_template('reset_password.html', token=token)

                # Hash the new password
                password_bytes = password.encode('utf-8')
                salt = bcrypt.gensalt()
                db_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

                # We are still in the original transaction.
                # Execute update and delete, then commit.
                update_pass_query = text("UPDATE users SET password = :password WHERE id = :user_id")
                conn.execute(update_pass_query, {"password": db_password, "user_id": user_id})

                delete_token_query = text("DELETE FROM password_reset_tokens WHERE token = :token")
                conn.execute(delete_token_query, {"token": token})
                
                conn.commit() # Commit password update and token deletion
                
                flash("Your password has been updated successfully! You can now log in.", "success")
                return redirect(url_for('login'))

            conn.rollback()
            return render_template('reset_password.html', token=token)

    except Exception as e:
        print(f"Error during password reset: {e}")
        flash("An error occurred while resetting your password. Please try again.", "danger")
        return redirect(url_for('login'))

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
                SELECT p.id, p.name, p.description, p.status, u.name AS business_name
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE p.user_id = :user_id
                ORDER BY p.id DESC
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
    if 'user_id' not in session:
        flash("You must be logged in to update your profile.", "danger")
        return redirect('/login')

    user_id = session.get('user_id')
    user_role = session.get('role')
    
    name = request.form.get('name', '').strip()

    try:
        with engine.connect() as conn:
            with conn.begin(): 
                query_name = text("UPDATE users SET name = :name WHERE id = :user_id")
                conn.execute(query_name, {"name": name, "user_id": user_id})

                if user_role == 1: 
                    bio = request.form.get('bio', '').strip()
                    query_bio = text("UPDATE users SET bio = :bio WHERE id = :user_id")
                    conn.execute(query_bio, {"bio": bio, "user_id": user_id})

                elif user_role == 3: 
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

    with engine.connect() as conn:
        user_data_query = text("SELECT name, bio FROM users WHERE id = :user_id")
        user_data = conn.execute(user_data_query, {"user_id": user_id}).mappings().first()

    if user_role == 3:
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
        applications = get_my_applications(user_id, engine)
        return render_template('profile.html', 
                                assignments=assignments, 
                                student_info=student_info,
                                instructors=instructors,
                                pending_request=pending_request,
                                user_data=user_data,
                                applications=applications) # Pass applications

    elif user_role == 0:
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

    elif user_role == 2:
        applications = get_my_applications(user_id, engine)
        return render_template('profile.html', user_data=user_data, applications=applications)
        
    else:
        return render_template('profile.html', user_data=user_data)

def create_admin_message(request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to send a message.", "warning")
        return redirect(url_for('login'))

    message = request.form.get('message')
    if not message or not message.strip():
        flash("Message cannot be empty.", "danger")
        return redirect(url_for('profile'))

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
