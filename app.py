import os
import bcrypt
import sqlalchemy
from sqlalchemy import text
from flask import Flask, render_template, request, redirect, url_for, flash, session
from api.auth import *
from api.projects import *
from api.mgt import *

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
        teams = get_teams_for_project(project_id, engine)
        return render_template('project.html', project=project, teams=teams)
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
    if 'user_id' not in session:
        flash("You need to be logged in to view this page.", "warning")
        return redirect(url_for('login'))
    
    if session['account_type'] == 3:
        assignments = get_projects_for_student(engine)
        return render_template('profile.html', assignments=assignments)
    else:
        projects = get_projects_for_user(engine)
        return render_template('profile.html', projects=projects)

@app.route('/userMgt')
def user_mgt():
    if 'user_id' not in session or session.get('account_type') != 0:
        flash("Access restricted to instructors.", "danger")
        return redirect(url_for('profile'))

    with engine.connect() as conn:
        instructor_id = session['user_id']

        # This query now fetches approved (status=1) projects for the dropdown
        projects_query = text("SELECT * FROM projects WHERE status = 1")
        projects_result = conn.execute(projects_query)
        projects = projects_result.mappings().all()

        students_query = text("SELECT id, email FROM users WHERE account_type = 3")
        students_result = conn.execute(students_query)
        all_students = students_result.mappings().all()

        teams_query = text("""
            SELECT t.id, t.name, t.project_id, p.name AS project_name
            FROM teams t
            JOIN projects p ON t.project_id = p.id
            WHERE t.user_id = :user_id
        """)
        teams_result = conn.execute(teams_query, {"user_id": instructor_id})
        teams = teams_result.mappings().all()

        team_members_query = text("SELECT team_id, user_id FROM team_members")
        team_members_result = conn.execute(team_members_query)
        team_members_map = {}
        for row in team_members_result.mappings().all():
            if row['team_id'] not in team_members_map:
                team_members_map[row['team_id']] = []
            team_members_map[row['team_id']].append(row['user_id'])
        
        assigned_student_ids = {item for sublist in team_members_map.values() for item in sublist}
        unassigned_students = [s for s in all_students if s['id'] not in assigned_student_ids]

        teams_with_members = []
        for team in teams:
            team_members_ids = team_members_map.get(team['id'], [])
            members = [s for s in all_students if s['id'] in team_members_ids]
            teams_with_members.append({**team, 'members': members})

    return render_template(
        'userMgt.html',
        projects=projects,
        unassigned_students=unassigned_students,
        teams_with_members=teams_with_members
    )

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

@app.route('/user/<int:user_id>/delete', methods=['POST'])
def delete_user_route(user_id):
    return delete_user(user_id, engine)

@app.route('/group/<int:team_id>/delete', methods=['POST'])
def delete_group_route(team_id):
    return delete_group(team_id, engine)

@app.route('/group/<int:team_id>/update', methods=['POST'])
def update_group_route(team_id):
    return update_group(team_id, engine)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
