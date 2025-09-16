import bcrypt
from sqlalchemy import text
from flask import request, flash, redirect, url_for, session

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
            query = text("SELECT id, email, password, account_type FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email}).mappings().first()

            if result:
                hashed_password_from_db = result.password.encode('utf-8')
                submitted_password_bytes = password.encode('utf-8')
                
                if bcrypt.checkpw(submitted_password_bytes, hashed_password_from_db):
                    session.clear()
                    session['user_id'] = result.id
                    session['email'] = result.email
                    session['account_type'] = result.account_type
                    flash(f"Welcome back, {email}!", "success")
                    return redirect(url_for('profile'))
            
            flash("Invalid email or password. Please try again.", "danger")

    except Exception as e:
        print(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again later.", "danger")

    return redirect(url_for('login'))
