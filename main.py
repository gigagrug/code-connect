import os
import sqlalchemy
import time
from sqlalchemy import text
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_socketio import SocketIO
from api.auth import *
from api.projects import *
from api.mgt import *
from api.invite import *
from api.chat import init_chat, init_application_chat
from api.admin import register_admin, login_admin, get_projects_paginated, get_users_paginated
from api.adminjobs import *
from api.adminmessages import *
from api.job import *
from schema.schema import DROP_SCHEMA_SQL, CREATE_SCHEMA_SQL
from schema.dummydata import seed_data


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
UPLOAD_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.debug = os.getenv("FLASK_DEBUG", "0") == "1"
db_url = os.getenv("DB_URL")

if not db_url:
    raise ValueError("Error: DB_URL environment variable is not set.")
engine = None
while engine is None:
    try:
        engine = sqlalchemy.create_engine(db_url)
        with engine.connect() as connection:
            print("Successfully connected to the database! 👍")
    except Exception as e:
        print(f"An error occurred while connecting to the database: {e}")
        print("Retrying connection in 5 seconds...")
        engine = None
        time.sleep(5)

def execute_raw_sql(db_engine, sql_script):
    statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
    if not statements:
        print("🤔 No statements found. Skipping.")
        return
    try:
        with db_engine.connect() as connection:
            with connection.begin() as transaction:
                connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                for statement in statements:
                    connection.execute(text(statement))
                connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
                print("✅ Successfully executed SQL batch.")
    except Exception as e:
        print(f"❌ Could not execute SQL batch. Error: {e}")
        raise

def manage_database_on_startup():
    if not engine:
        print("❌ Database engine not initialized. Skipping schema management.")
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    if app.debug:
        print("🚀 Starting **DEBUG** database reset (Drop/Create)...")
        try:
            execute_raw_sql(engine, DROP_SCHEMA_SQL)
            execute_raw_sql(engine, CREATE_SCHEMA_SQL)
            seed_data(engine)
            print("\n🎉 Database has been successfully **RESET! 🎉\n")
        except Exception as e:
            print(f"\n🔥 Database reset failed: {e} 🔥")
    else:
        print("Production mode detected (FLASK_DEBUG=0). Starting **CREATE ONLY** schema run.")
        try:
            execute_raw_sql(engine, CREATE_SCHEMA_SQL)
            print("✅ CREATE_SCHEMA_SQL executed. Existing data preserved.")
        except Exception as e:
            print(f"⚠️ Could not execute CREATE_SCHEMA_SQL. Check database logs for details: {e}")

manage_database_on_startup() 

socketio = SocketIO(app)
init_chat(socketio, engine)
init_application_chat(socketio, engine) 

@app.route('/uploads/<path:project_name>/<path:filename>')
def serve_upload(project_name, filename):
    project_dir = os.path.join(app.config['UPLOAD_DIR'], project_name)
    return send_from_directory(project_dir, filename)

@app.route('/admin')
def admin_index():
    if 'user_id' not in session or session.get('role') != 10:
        flash("Access denied. You must be an admin to view this page.", "danger")
        return redirect(url_for('admin_login'))

    page = request.args.get('page', default=1, type=int) or 1
    per_page = 6
    projects, total, total_pages, pending_count, approved_count, taken_count = get_projects_paginated(engine, page=page, per_page=per_page)
    if page > total_pages:
        page = total_pages
    return render_template('/admin/admin.html', projects=projects, page=page, per_page=per_page, total=total, total_pages=total_pages, pending_count=pending_count, approved_count=approved_count, taken_count=taken_count)

@app.route('/admin/register', methods=['POST', 'GET'])
def admin_register():
    if request.method == 'POST':
        return register_admin(request, engine)
    return render_template('/admin/adminregister.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        return login_admin(request, engine)
    return render_template('/admin/adminlogin.html')

@app.route('/admin/jobs', endpoint='adminjobs')
def admin_jobs_index():
    if 'user_id' not in session or session.get('role') != 10:
        flash("You must be logged in as an admin to access admin jobs.", "warning")
        return redirect(url_for('admin_login'))

    page = request.args.get('page', default=1, type=int) or 1
    per_page = 6
    jobs, total, total_pages, pending_count, approved_count, taken_count = get_jobs_paginated(engine, page=page, per_page=per_page)
    if page > total_pages:
        page = total_pages
    return render_template('/admin/adminjobs.html', jobs=jobs, page=page, per_page=per_page, total=total, total_pages=total_pages, pending_count=pending_count, approved_count=approved_count, taken_count=taken_count)

@app.route('/admin/users', endpoint='adminusers')
def admin_users_index():
    if 'user_id' not in session or session.get('role') != 10:
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin_login'))

    page = request.args.get('page', default=1, type=int) or 1
    per_page = 6
    users, total, total_pages, pending_count, approved_count, taken_count = get_users_paginated(engine, page=page, per_page=per_page)
    return render_template('/admin/adminusers.html', users=users, page=page, per_page=per_page, total=total, total_pages=total_pages, pending_count=pending_count, approved_count=approved_count, taken_count=taken_count)

@app.route('/admin/messages', endpoint='adminmessages')
def admin_messages_index():
    if 'user_id' not in session or session.get('role') != 10:
        flash("You must be logged in as an admin to view admin messages.", "warning")
        return redirect(url_for('admin_login'))

    messages = get_admin_messages(engine)
    return render_template('/admin/adminmessages.html', admin_messages=messages)

@app.route('/admin/jobs/<int:job_id>/update', methods=['POST'])
def admin_job_update(job_id):
    if 'user_id' not in session or session.get('role') != 10:
        return jsonify({"error": "Unauthorized"}), 403

    status = request.form.get('status', type=int)
    if status not in (0, 1, 2):
        return jsonify({"error": "Invalid status"}), 400
    ok = admin_update_job_status(engine, job_id, status)
    if not ok:
        return jsonify({"error": "Update failed"}), 500
    return jsonify({"ok": True, "job_id": job_id, "status": status})

@app.route('/admin/jobs/<int:job_id>/delete', methods=['POST'])
def admin_job_delete(job_id):
    if 'user_id' not in session or session.get('role') != 10:
        return jsonify({"error": "Unauthorized"}), 403

    ok = admin_delete_job(engine, job_id)
    if not ok:
        return jsonify({"error": "Delete failed"}), 500
    return jsonify({"ok": True, "job_id": job_id})

# Users
@app.route('/', methods=['GET'])
def index():
    if 'user_id' in session:
        if session.get('role') == 1:
            return redirect(url_for('business_profile', user_id=session['user_id']))
        if session.get('role') == 2:        
            return redirect(url_for('jobs_page'))
        if session.get('role') == 3:
            student_projects = get_projects_for_student(engine)
            if student_projects:
                first_project_id = student_projects[0]['project_id']
                return redirect(url_for('project_page', project_id=first_project_id))
        
        # Get Params for initial load if present in URL
        search = request.args.get('search', None)
        status_filter = request.args.get('status', None)
        sort = request.args.get('sort', 'desc')
        
        projects = get_all_projects(engine, session, page=1, per_page=12, search_query=search, status_filter=status_filter, sort_order=sort)
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
          
        can_chat = check_if_user_can_chat(user_id, project_id, engine)
        can_edit_links = check_if_user_can_edit_links(user_id, project, engine)
        can_comment = check_if_user_can_comment(user_id, project, engine)

        teams = get_teams_for_project(project_id, engine)
        comments = get_comments_for_project(project_id, engine, session)
        chat_history = []
          
        if can_chat:
            with engine.connect() as conn:
                history_query = text("""
                    SELECT c.id AS message_id, u.email, c.message_text, c.timestamp, c.attachment_path
                    FROM chat_messages c JOIN users u ON c.user_id = u.id
                    WHERE c.project_id = :project_id ORDER BY c.timestamp ASC
                """)
                chat_history = conn.execute(history_query, {"project_id": project_id}).all()

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
      
    if session.get('role') not in [2, 3]:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('index'))
          
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
        applications = []
        my_application = None 
          
        if session.get('user_id') == job.user_id:
            applications = get_job_applications(job_id, engine)
          
        elif session.get('role') in [2, 3]:
            with engine.connect() as conn:
                query = text("SELECT * FROM job_applications WHERE job_id = :job_id AND user_id = :user_id")
                my_application = conn.execute(query, {"job_id": job_id, "user_id": session.get('user_id')}).mappings().first()
                  
        return render_template('job.html', job=job, applications=applications, my_application=my_application)
    else:
        flash("Job not found.", "danger")
        return redirect(url_for('index'))

@app.route('/job/<int:job_id>/update', methods=['POST'])
def job_update_route(job_id):
    return update_job(job_id, request, engine)

@app.route('/job/<int:job_id>/delete', methods=['POST'])
def job_delete_route(job_id):
    return delete_job(job_id, engine)

@app.route('/job/<int:job_id>/apply', methods=['POST'])
def apply_to_job_route(job_id):
    return apply_to_job(job_id, request, engine)

@app.route('/project/<int:project_id>/comment', methods=['POST'])
def project_comment_route(project_id):
    return add_comment_to_project(project_id, request, engine)

@app.route('/project/<int:project_id>/comment/<int:comment_id>/delete', methods=['POST'])
def project_comment_delete_route(project_id, comment_id):
    return delete_comment_on_project(project_id, comment_id, engine)

@app.route('/project/<int:project_id>/instructor-manage-files', methods=['POST'])
def instructor_files_route(project_id):
    return instructor_manage_files(project_id, request, engine)

@app.route('/project/<int:project_id>/file/rename', methods=['POST'])
def rename_file_route(project_id):
    return rename_project_attachment(project_id, request, engine)

@app.route('/application/<int:application_id>')
def view_application(application_id):
    if 'user_id' not in session:
        flash("You must be logged in to view this page.", "warning")
        return redirect(url_for('login'))
          
    app_data = get_application_by_id(application_id, engine)
      
    if not app_data:
        flash("Application not found or you do not have permission to view it.", "danger")
        return redirect(url_for('index'))
          
    chat_history = get_application_chat_history(application_id, engine)
      
    return render_template(
        'application.html',
        application=app_data,
        chat_history=chat_history
    )

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
    return get_profile_data(engine)

@app.route('/profile/update', methods=['POST'])
def profile_update_route():
    return update_profile(engine)

@app.route('/message/admin', methods=['POST'])
def admin_message_route():
    return create_admin_message(request, engine)

@app.route('/business/<int:user_id>', methods=['GET'])
def business_profile(user_id):
    profile_page = get_business_profile_data(user_id, engine)
    if profile_page is None:
        return redirect(url_for('index'))
    return profile_page

@app.route('/business/<int:user_id>/jobs', methods=['GET'])
def business_jobs(user_id):
    profile_page = get_business_jobs_data(user_id, engine)
    if profile_page is None:
        return redirect(url_for('index'))
    return profile_page

@app.route('/classroom', methods=['GET'])
def user_mgt():
    if 'user_id' not in session or session.get('role') != 0:
        flash("Access restricted to instructors.", "danger")
        return redirect(url_for('profile'))
    return get_user_mgt_data(engine)

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

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    return handle_forgot_password(request, engine) 

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    return handle_reset_password(request, engine, token)

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
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
