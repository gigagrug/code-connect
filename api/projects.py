from sqlalchemy import text
from flask import flash, redirect, url_for, session

def create_project(request, engine):
    if 'email' not in session:
        flash("You must be logged in to create a project.", "warning")
        return redirect(url_for('login'))

    if session.get('account_type') == 3:
        flash("You do not have permission to create projects.", "danger")
        return redirect(url_for('index'))

    project_name = request.form.get('name')
    project_description = request.form.get('description')

    if not project_name or not project_description:
        flash("Project name and description are required.", "danger")
        return redirect(url_for('index'))

    try:
        with engine.connect() as connection:
            user_query = text("SELECT id FROM users WHERE email = :email")
            user_result = connection.execute(user_query, {"email": session['email']}).fetchone()

            if not user_result:
                flash("Could not find user. Please log in again.", "danger")
                return redirect(url_for('login'))
            
            user_id = user_result.id

            approved = False
            if session.get('account_type') == 0:
                approved = True

            insert_query = text(
                    "INSERT INTO projects (user_id, name, description, approved) VALUES (:user_id, :name, :description, :approved)"
            )
            params = {
                "user_id": user_id,
                "name": project_name,
                "description": project_description,
                "approved": approved
            }
            connection.execute(insert_query, params)
            connection.commit()
            flash("New project created successfully!", "success")

    except Exception as e:
        print(f"Database error during project creation: {e}")
        flash("An error occurred while creating the project. Please try again later.", "danger")

    return redirect(url_for('index'))

def update_project(project_id, request, engine):
    if 'email' not in session:
        flash("You must be logged in to update a project.", "warning")
        return redirect(url_for('login'))

    project = get_project_by_id(project_id, engine)
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

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
            user_query = text("SELECT id FROM users WHERE email = :email")
            user_id = connection.execute(user_query, {"email": session['email']}).fetchone().id
            
            update_query = text("UPDATE projects SET name = :name, description = :description WHERE id = :project_id AND user_id = :user_id")
            params = {"name": new_name, "description": new_description, "project_id": project_id, "user_id": user_id}
            connection.execute(update_query, params)
            connection.commit()
            flash("Project updated successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while updating the project: {e}", "danger")
    
    return redirect(url_for('project_page', project_id=project_id))

def approve_project(project_id, engine):
    if session.get('account_type') != 0:
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    project = get_project_by_id(project_id, engine)
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))
    new_status = not project.approved
    try:
        with engine.connect() as connection:
            update_query = text("UPDATE projects SET approved = :status WHERE id = :project_id")
            connection.execute(update_query, {"status": new_status, "project_id": project_id})
            connection.commit()
            if new_status:
                flash("Project approved and is now public.", "success")
            else:
                flash("Project has been unapproved and is now hidden.", "warning")
    except Exception as e:
        flash(f"An error occurred while updating the project's status: {e}", "danger")
    return redirect(url_for('project_page', project_id=project_id))

def delete_project(project_id, engine):
    if 'email' not in session:
        flash("You must be logged in to delete a project.", "warning")
        return redirect(url_for('login'))

    project = get_project_by_id(project_id, engine)
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

    if project.email != session['email']:
        flash("You do not have permission to delete this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        with engine.connect() as connection:
            user_query = text("SELECT id FROM users WHERE email = :email")
            user_id = connection.execute(user_query, {"email": session['email']}).fetchone().id

            delete_query = text("DELETE FROM projects WHERE id = :project_id AND user_id = :user_id")
            connection.execute(delete_query, {"project_id": project_id, "user_id": user_id})
            connection.commit()
            flash("Project deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred while deleting the project: {e}", "danger")
        return redirect(url_for('project_page', project_id=project_id))
        
    return redirect(url_for('index'))

def get_projects_for_user(engine):
    if 'email' not in session:
        return []

    try:
        with engine.connect() as connection:
            user_query = text("SELECT id FROM users WHERE email = :email")
            user_result = connection.execute(user_query, {"email": session['email']}).fetchone()

            if not user_result:
                return []
            
            user_id = user_result.id

            project_query = text("SELECT id, name, description FROM projects WHERE user_id = :user_id")
            projects = connection.execute(project_query, {"user_id": user_id}).fetchall()
            return projects

    except Exception as e:
        print(f"Database error fetching projects: {e}")
        return []

def get_all_projects(engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT p.id, p.name, p.description, p.approved, u.email, u.account_type 
                FROM projects p
                JOIN users u ON p.user_id = u.id
                ORDER BY p.id DESC
            """)
            projects = connection.execute(query).fetchall()
            return projects
    except Exception as e:
        print(f"Database error fetching all projects: {e}")
        return []

def get_project_by_id(project_id, engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT p.id, p.name, p.description, p.approved, u.email, u.account_type
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = :project_id
            """)
            result = connection.execute(query, {"project_id": project_id}).fetchone()
            return result
    except Exception as e:
        print(f"Database error fetching project by ID: {e}")
        return None
