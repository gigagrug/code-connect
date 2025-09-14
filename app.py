import os
import bcrypt
import sqlalchemy
from sqlalchemy import text
from flask import Flask, render_template, request, redirect, url_for, flash, session
from api.auth import *
from api.projects import *

db_url = os.getenv("DB_URL")
if not db_url:
    raise ValueError("Error: DB_URL environment variable is not set.")

try:
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as connection:
        print("Successfully connected to the database! 👍")
except Exception as e:
    print(f"An error occurred while connecting to the database: {e}")
    engine = None

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", 'a_default_dev_secret_key')


@app.route('/')
def index():
    projects = get_all_projects(engine)
    return render_template('index.html', projects=projects)

@app.route('/projects/create', methods=['POST'])
def project_create_route():
    return create_project(request, engine)

@app.route('/project/<int:project_id>')
def project_page(project_id):
    project = get_project_by_id(project_id, engine)
    if project:
        return render_template('project.html', project=project)
    else:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

@app.route('/project/<int:project_id>/update', methods=['POST'])
def project_update_route(project_id):
    return update_project(project_id, request, engine)

@app.route('/project/<int:project_id>/approve', methods=['POST'])
def project_approve_route(project_id):
    return approve_project(project_id, engine)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
def project_delete_route(project_id):
    return delete_project(project_id, engine)

@app.route('/profile')
def profile():
    if 'email' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
    
    projects = get_projects_for_user(engine)
    return render_template('profile.html', email=session['email'], projects=projects)

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        return register_user(request, engine)
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return login_user(request, engine)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
