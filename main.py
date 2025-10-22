import os
import sys
import bcrypt
import sqlalchemy
from sqlalchemy import text
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_socketio import SocketIO
from api.auth import *
from api.projects import *
from api.mgt import *
from api.invite import *
from api.chat import *
from api.admin import *
from api.job import *

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", 'a_default_dev_secret_key')
UPLOAD_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
app.config['UPLOAD_DIR'] = UPLOAD_DIR
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

def drop_all_tables(db_engine, file_path):
    print(f"--- Dropping tables using rollback script from: {file_path} ---")
    if not os.path.exists(file_path):
        print(f"❌ Error: SQL file not found at '{file_path}'")
        raise FileNotFoundError
    with open(file_path, 'r', encoding='utf-8') as file:
        full_script = file.read()
    rollback_marker = "-- schema rollback"
    if rollback_marker not in full_script:
        print(f"❌ Error: Rollback marker '{rollback_marker}' not found in {file_path}.")
        raise ValueError("Rollback marker not found")
    rollback_script = full_script.split(rollback_marker, 1)[1]
    statements = [stmt.strip() for stmt in rollback_script.split(';') if stmt.strip()]
    if not statements:
        print("🤔 No rollback statements found to execute.")
        return
    try:
        with db_engine.connect() as connection:
            with connection.begin() as transaction:
                connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                for statement in statements:
                    connection.execute(text(statement))
                connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
                print("✅ All tables dropped successfully based on rollback script.")
    except Exception as e:
        print(f"❌ Could not complete dropping tables. Error: {e}")
        raise

def execute_sql_from_file(db_engine, file_path):
    print(f"--- Executing SQL from: {file_path} ---")
    if not os.path.exists(file_path):
        print(f"❌ Error: SQL file not found at '{file_path}'")
        raise FileNotFoundError
    with open(file_path, 'r', encoding='utf-8') as file:
        sql_script = file.read()
    rollback_marker = "-- schema rollback"
    if rollback_marker in sql_script:
        print(f"  -> Rollback marker found. Executing creation part only.")
        sql_script = sql_script.split(rollback_marker, 1)[0]
    statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
    try:
        with db_engine.connect() as connection:
            with connection.begin() as transaction:
                for statement in statements:
                    connection.execute(text(statement))
                print(f"✅ Successfully executed SQL from {os.path.basename(file_path)}.")
    except Exception as e:
        print(f"❌ Could not execute SQL file. Error: {e}")
        raise

def reset_database_on_startup():
    if not engine:
        print("❌ Database engine not initialized. Skipping reset.")
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("🚀 Starting database reset process on server startup...")
        try:
            schema_file = './schema/migrations/1_schema.sql'
            data_file = './schema/data/0_data.sql'
            drop_all_tables(engine, schema_file)
            execute_sql_from_file(engine, schema_file)
            execute_sql_from_file(engine, data_file)
            print("\n🎉 Database has been successfully reset and seeded! 🎉\n")
        except Exception as e:
            print(f"\n🔥 Database reset failed: {e} 🔥")
            sys.exit(1)

if app.debug:
    reset_database_on_startup()

socketio = SocketIO(app)
init_chat(socketio, engine)
@app.route('/uploads/<path:project_name>/<path:filename>')
def serve_upload(project_name, filename):
    project_dir = os.path.join(app.config['UPLOAD_DIR'], project_name)
    return send_from_directory(project_dir, filename)
# Admin
## create routes only under '/admin/'
@app.route('/admin')
def admin():
    page = int(request.args.get('page', 1) or 1)
    per_page = 25
    projects, total, total_pages = get_projects_paginated(engine, page=page, per_page=per_page)
    return render_template('admin/admin.html', projects=projects, page=page, per_page=per_page, total=total, total_pages=total_pages)
# Users
@app.route('/')
def index():
    if 'user_id' in session:
        projects = get_all_projects(engine, session, page=1, per_page=12)
        return render_template('index.html', projects=projects)
    else:
        return render_template('landing_page.html')

@app.route('/api/load-projects')
def projects_api_route():
    return load_projects_html(engine)

@app.route('/project/<int:project_id>', methods=['GET'])
def project_page(project_id):
    if 'user_id' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
    
    project = get_project_by_id(project_id, engine)
    if project:
        user_id = session.get('user_id')
        
        # Permissions
        can_chat = check_if_user_can_chat(user_id, project_id, engine)
        can_edit_links = check_if_user_can_edit_links(user_id, project, engine)
        can_comment = check_if_user_can_comment(user_id, project, engine)

        # Data
        teams = get_teams_for_project(project_id, engine)
        comments = get_comments_for_project(project_id, engine)
        chat_history = []
        
        if can_chat:
            with engine.connect() as conn:
                history_query = text("""
                    SELECT c.id AS message_id, u.email, c.message_text, c.timestamp
                    FROM chat_messages c JOIN users u ON c.user_id = u.id
                    WHERE c.project_id = :project_id ORDER BY c.timestamp ASC
                """)
                chat_history = conn.execute(history_query, {"project_id": project_id}).all()

        # Check if the current instructor has this project marked as 'pending'
        is_pending_by_current_instructor = False
        if session.get('role') == 0:
            with engine.connect() as conn:
                query = text("""
                    SELECT 1 FROM instructor_projects
                    WHERE instructor_id = :instructor_id 
                      AND project_id = :project_id 
                      AND status = 1
                """)
                result = conn.execute(query, {
                    "instructor_id": session['user_id'],
                    "project_id": project_id
                }).first()
                if result:
                    is_pending_by_current_instructor = True
        
        return render_template(
            'project.html', 
            project=project, 
            teams=teams, 
            can_edit_links=can_edit_links, 
            can_chat=can_chat, 
            chat_history=chat_history,
            is_pending_by_current_instructor=is_pending_by_current_instructor,
            can_comment=can_comment,
            comments=comments
        )
    else:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

@app.route('/project/create', methods=['POST'])
def project_create_route():
    return create_project(request, engine)

@app.route('/project/<int:project_id>/update', methods=['POST'])
def project_update_route(project_id):
    return update_project(project_id, request, engine)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
def project_delete_route(project_id):
    return delete_project(project_id, engine)

@app.route('/project/<int:project_id>/approve', methods=['POST'])
def project_approve_route(project_id):
    return approve_project(project_id, engine)

@app.route('/project/<int:project_id>/links', methods=['POST'])
def project_links_route(project_id):
    return update_project_links(project_id, engine)

@app.route('/jobs')
def jobs_page():
    if 'user_id' not in session:
        flash("You must be logged in to view this page.", "warning")
        return redirect(url_for('login'))
        
    open_jobs = get_open_jobs(engine)
    return render_template('jobs.html', jobs=open_jobs)

@app.route('/job/create', methods=['POST'])
def job_create_route():
    return create_job(request, engine)

@app.route('/job/<int:job_id>', methods=['GET'])
def job_page(job_id):
    if 'user_id' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
        
    job = get_job_by_id(job_id, engine)
    if job:
        return render_template('job.html', job=job)
    else:
        flash("Job not found.", "danger")
        return redirect(url_for('index'))

@app.route('/job/<int:job_id>/update', methods=['POST'])
def job_update_route(job_id):
    return update_job(job_id, request, engine)

@app.route('/job/<int:job_id>/delete', methods=['POST'])
def job_delete_route(job_id):
    return delete_job(job_id, engine)

@app.route('/project/<int:project_id>/comment', methods=['POST'])
def project_comment_route(project_id):
    return add_comment_to_project(project_id, request, engine)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
    return get_profile_data(engine)

@app.route('/profile/update', methods=['POST'])
def profile_update_route():
    return update_profile(engine)

@app.route('/business/<int:user_id>')
def business_profile(user_id):
    profile_page = get_business_profile_data(user_id, engine)
    if profile_page is None:
        return redirect(url_for('index'))
    return profile_page

@app.route('/userMgt')
def user_mgt():
    if 'user_id' not in session or session.get('role') != 0:
        flash("Access restricted to instructors.", "danger")
        return redirect(url_for('profile'))
    return get_user_mgt_data(engine)

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        return register_user(request, engine, app.debug)
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return login_user(request, engine, app.debug)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('login'))

@app.route('/user/create', methods=['POST'])
def create_user_route():
    return create_user_by_instructor(engine)

@app.route('/group/create', methods=['POST'])
def create_group_route():
    return create_group(engine)
    
@app.route('/group/assign', methods=['POST'])
def assign_user_route():
    return assign_user_to_team(engine)

@app.route('/group/<int:team_id>/assign_project', methods=['POST'])
def assign_project_route(team_id):
    return assign_project_to_group(team_id, engine)

@app.route('/user/<int:user_id>/delete', methods=['POST'])
def delete_user_route(user_id):
    return delete_user(user_id, engine)

@app.route('/group/<int:team_id>/delete', methods=['POST'])
def delete_group_route(team_id):
    return delete_group(team_id, engine)

@app.route('/group/<int:team_id>/update', methods=['POST'])
def update_group_route(team_id):
    return update_group(team_id, engine)

@app.route('/request/instructor', methods=['POST'])
def request_instructor_route():
    return send_instructor_request(engine)

@app.route('/request/cancel', methods=['POST'])
def cancel_request_route():
    return cancel_instructor_request(engine)

@app.route('/request/handle/<int:request_id>', methods=['POST'])
def handle_request_route(request_id):
    return handle_instructor_request(request_id, engine)

@app.route('/request/dismiss/<int:request_id>', methods=['POST'])
def dismiss_request_route(request_id):
    return dismiss_denied_request(request_id, engine)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
