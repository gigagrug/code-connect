import os
import bcrypt
import sqlalchemy
from sqlalchemy import text
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO
from api.auth import *
from api.projects import *
from api.mgt import *
from api.invite import *
from api.chat import *

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

socketio = SocketIO(app)

init_chat(socketio, engine)

# Admin


# Users
@app.route('/')
def index():
    projects = get_all_projects(engine, page=1, per_page=25)
    return render_template('index.html', projects=projects)

@app.route('/api/projects')
def projects_api_route():
    return get_projects_api(engine)

@app.route('/projects/create', methods=['POST'])
def project_create_route():
    return create_project(request, engine)

@app.route('/project/<int:project_id>')
def project_page(project_id):
    project = get_project_by_id(project_id, engine)
    if project:
        can_chat = check_if_user_can_chat(session.get('user_id'), project_id, engine)
        chat_history = []
        if can_chat:
            with engine.connect() as conn:
                history_query = text("""
                    SELECT 
                        c.id AS message_id,
                        u.email, 
                        c.message_text, 
                        c.timestamp
                    FROM chat_messages c JOIN users u ON c.user_id = u.id
                    WHERE c.project_id = :project_id ORDER BY c.timestamp ASC
                """)
                chat_history = conn.execute(history_query, {"project_id": project_id}).all()

        teams = get_teams_for_project(project_id, engine)
        can_edit_links = check_if_user_can_edit_links(session.get('user_id'), project, engine)
        return render_template('project.html', 
                               project=project, 
                               teams=teams,
                               can_edit_links=can_edit_links,
                               can_chat=can_chat,
                               chat_history=chat_history)
    else:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

@app.route('/project/<int:project_id>/links', methods=['POST'])
def project_links_route(project_id):
    return update_project_links(project_id, engine)

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
    if 'user_id' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
    return get_profile_data(engine)

@app.route('/userMgt')
def user_mgt():
    if 'user_id' not in session or session.get('account_type') != 0:
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
