from sqlalchemy import text
from flask import flash, redirect, url_for, session

def create_project(request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to create a project.", "warning")
        return redirect(url_for('login'))

    if session.get('account_type') == 3:
        flash("You do not have permission to create projects.", "danger")
        return redirect(url_for('index'))

    project_name = request.form.get('name')
    project_description = request.form.get('description')
    user_id = session['user_id']

    if not project_name or not project_description:
        flash("Project name and description are required.", "danger")
        return redirect(url_for('profile'))

    # Status is 1 (approved) if created by an instructor, otherwise 0 (pending)
    status = 1 if session.get('account_type') == 0 else 0

    try:
        with engine.connect() as connection:
            insert_query = text(
                "INSERT INTO projects (user_id, name, description, status) VALUES (:user_id, :name, :description, :status)"
            )
            params = {
                "user_id": user_id,
                "name": project_name,
                "description": project_description,
                "status": status
            }
            connection.execute(insert_query, params)
            connection.commit()
            flash("New project created successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while creating the project: {e}", "danger")

    return redirect(url_for('profile'))

def approve_project(project_id, engine):
    if session.get('account_type') != 0:
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    
    project = get_project_by_id(project_id, engine)
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

    # If status is 0 (pending), approve it (set to 1). Otherwise, unapprove it (set to 0).
    new_status = 1 if project.status == 0 else 0
    
    try:
        with engine.connect() as connection:
            update_query = text("UPDATE projects SET status = :status WHERE id = :project_id")
            connection.execute(update_query, {"status": new_status, "project_id": project_id})
            connection.commit()
            if new_status == 1:
                flash("Project approved and is now public.", "success")
            else:
                flash("Project has been unapproved and is now hidden.", "warning")
    except Exception as e:
        flash(f"An error occurred while updating the project's status: {e}", "danger")
    return redirect(url_for('project_page', project_id=project_id))

def get_projects_for_user(engine):
    if 'user_id' not in session:
        return []

    user_id = session['user_id']
    try:
        with engine.connect() as connection:
            project_query = text("""
                SELECT
                    p.id, p.name, p.description, p.status,
                    u.email, u.account_type,
                    COUNT(t.id) AS team_count
                FROM projects p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN teams t ON p.id = t.project_id
                WHERE p.user_id = :user_id
                GROUP BY p.id, u.email, u.account_type
                ORDER BY p.id DESC
            """)
            projects = connection.execute(project_query, {"user_id": user_id}).mappings().all()
            return projects

    except Exception as e:
        print(f"Database error fetching user projects: {e}")
        return []

def get_all_projects(engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    p.id, p.name, p.description, p.status, 
                    u.email, u.account_type
                FROM projects p
                JOIN users u ON p.user_id = u.id
                ORDER BY p.id DESC
            """)
            projects = connection.execute(query).mappings().all()
            return projects
    except Exception as e:
        print(f"Database error fetching all projects: {e}")
        return []

def get_project_by_id(project_id, engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT p.id, p.name, p.description, p.status, u.email, u.account_type
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = :project_id
            """)
            result = connection.execute(query, {"project_id": project_id}).mappings().first()
            return result
    except Exception as e:
        print(f"Database error fetching project by ID: {e}")
        return None

def get_projects_for_student(engine):
    if 'user_id' not in session:
        return []
    user_id = session['user_id']
    try:
        with engine.connect() as conn:
            student_teams_query = text("""
                SELECT p.id as project_id, p.name as project_name, p.description as project_description,
                       t.id as team_id, t.name as team_name
                FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                JOIN projects p ON t.project_id = p.id
                WHERE tm.user_id = :user_id AND p.status IN (1, 2)
            """)
            student_project_info = conn.execute(student_teams_query, {"user_id": user_id}).mappings().all()
            assignments = []
            for info in student_project_info:
                team_members_query = text("SELECT u.email FROM team_members tm JOIN users u ON tm.user_id = u.id WHERE tm.team_id = :team_id ORDER BY u.email")
                members_result = conn.execute(team_members_query, {"team_id": info['team_id']}).mappings().all()
                assignment_data = dict(info)
                assignment_data['members'] = members_result
                assignments.append(assignment_data)
            return assignments
    except Exception as e:
        print(f"Database error fetching student projects: {e}")
        return []

def get_teams_for_project(project_id, engine):
    try:
        with engine.connect() as conn:
            teams_query = text("SELECT id, name FROM teams WHERE project_id = :project_id ORDER BY name")
            teams_result = conn.execute(teams_query, {"project_id": project_id}).mappings().all()
            teams_with_members = []
            for team in teams_result:
                members_query = text("SELECT u.email FROM team_members tm JOIN users u ON tm.user_id = u.id WHERE tm.team_id = :team_id ORDER BY u.email")
                members_result = conn.execute(members_query, {"team_id": team['id']}).mappings().all()
                teams_with_members.append({"name": team['name'], "members": members_result})
            return teams_with_members
    except Exception as e:
        print(f"Database error fetching teams for project: {e}")
        return []

# Note: update_project and delete_project did not need changes related to status
def update_project(project_id, request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to update a project.", "warning")
        return redirect(url_for('login'))
    project = get_project_by_id(project_id, engine)
    if project.email != session['email']:
        flash("You do not have permission to edit this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    new_name = request.form.get('name')
    new_description = request.form.get('description')
    if not new_name or not new_description:
        flash("Project name and description cannot be empty.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    try:
        with engine.connect() as connection:
            update_query = text("UPDATE projects SET name = :name, description = :description WHERE id = :project_id AND user_id = :user_id")
            params = {"name": new_name, "description": new_description, "project_id": project_id, "user_id": session['user_id']}
            connection.execute(update_query, params)
            connection.commit()
            flash("Project updated successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while updating the project: {e}", "danger")
    return redirect(url_for('project_page', project_id=project_id))

def delete_project(project_id, engine):
    if 'user_id' not in session:
        flash("You must be logged in to delete a project.", "warning")
        return redirect(url_for('login'))
    project = get_project_by_id(project_id, engine)
    if project.email != session['email']:
        flash("You do not have permission to delete this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    try:
        with engine.connect() as connection:
            delete_query = text("DELETE FROM projects WHERE id = :project_id AND user_id = :user_id")
            connection.execute(delete_query, {"project_id": project_id, "user_id": session['user_id']})
            connection.commit()
            flash("Project deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred while deleting the project: {e}", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    return redirect(url_for('index'))
