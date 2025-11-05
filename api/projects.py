import os
import uuid
import shutil
from sqlalchemy import text
from flask import flash, redirect, url_for, session, request, jsonify, render_template
from werkzeug.utils import secure_filename

def _get_upload_paths(project_name, original_filename):
    sanitized_project_name = secure_filename(str(project_name))[:50]
    safe_filename = secure_filename(original_filename)
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    
    fs_upload_dir = os.path.join('.', 'uploads', sanitized_project_name)
    os.makedirs(fs_upload_dir, exist_ok=True)
    
    fs_save_path = os.path.join(fs_upload_dir, unique_filename)
    url_path = f"/uploads/{sanitized_project_name}/{unique_filename}"
    
    return (fs_save_path, url_path)


def get_project_by_id(project_id, engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    p.id, p.name, p.description, p.status, 
                    p.project_link, p.github_link, p.attachment_path,
                    u.name as business_name, u.role, u.id as user_id
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = :project_id
            """)
            result = connection.execute(query, {"project_id": project_id}).mappings().first()
            return result
    except Exception as e:
        print(f"Database error fetching project by ID: {e}")
        return None

def create_project(request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to create a project.", "warning")
        return redirect(url_for('login'))

    if session.get('permission') != 1:
        flash("You do not have permission to create projects.", "danger")
        return redirect(url_for('index'))

    project_name = request.form.get('name')
    project_description = request.form.get('description')
    user_id = session['user_id']

    if not project_name or not project_description:
        flash("Project name and description are required.", "danger")
        return redirect(url_for('business_profile', user_id=session['user_id']))

    status = 1 if session.get('role') == 0 else 0
    
    attachment_paths = []
    files = request.files.getlist('attachment') 

    for file in files:
        if file and file.filename:
            try:
                fs_save_path, url_path = _get_upload_paths(project_name, file.filename)
                file.save(fs_save_path)
                attachment_paths.append(url_path) 
            except Exception as e:
                flash(f"Error saving file {file.filename}: {e}", "danger")
                return redirect(url_for('business_profile', user_id=session['user_id']))

    attachment_path_str = ";".join(attachment_paths) if attachment_paths else None

    try:
        with engine.connect() as connection:
            insert_query = text(
                "INSERT INTO projects (user_id, name, description, status, attachment_path) VALUES (:user_id, :name, :description, :status, :attachment_path)"
            )
            params = {
                "user_id": user_id,
                "name": project_name,
                "description": project_description,
                "status": status,
                "attachment_path": attachment_path_str 
            }
            connection.execute(insert_query, params)
            connection.commit()
            flash("New project created successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while creating the project: {e}", "danger")

    return redirect(url_for('business_profile', user_id=session['user_id']))

def approve_project(project_id, engine):
    if session.get('role') != 0:
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    instructor_id = session.get('user_id')
    new_status_str = request.form.get('new_status')

    if not new_status_str or not new_status_str.isdigit():
        flash("Invalid status provided.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    new_status = int(new_status_str)
    if new_status not in [0, 1, 2]:
        flash("Invalid status value. Please select a valid option.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        with engine.connect() as connection:
            if new_status == 2:
                clear_other_instructors_query = text("""
                    DELETE FROM instructor_projects
                    WHERE project_id = :project_id AND instructor_id != :instructor_id
                """)
                connection.execute(clear_other_instructors_query, {
                    "project_id": project_id,
                    "instructor_id": instructor_id
                })

                upsert_query = text("""
                    INSERT INTO instructor_projects (instructor_id, project_id, status)
                    VALUES (:instructor_id, :project_id, :status)
                    ON DUPLICATE KEY UPDATE status = :status
                """)
                connection.execute(upsert_query, {
                    "instructor_id": instructor_id,
                    "project_id": project_id,
                    "status": new_status
                })

            elif new_status == 1:
                upsert_query = text("""
                    INSERT INTO instructor_projects (instructor_id, project_id, status)
                    VALUES (:instructor_id, :project_id, :status)
                    ON DUPLICATE KEY UPDATE status = :status
                """)
                connection.execute(upsert_query, {
                    "instructor_id": instructor_id,
                    "project_id": project_id,
                    "status": new_status
                })

            else:  
                delete_query = text("""
                    DELETE FROM instructor_projects
                    WHERE instructor_id = :instructor_id AND project_id = :project_id
                """)
                connection.execute(delete_query, {
                    "instructor_id": instructor_id,
                    "project_id": project_id
                })

            update_project_query = text("UPDATE projects SET status = :status WHERE id = :project_id")
            connection.execute(update_project_query, {"status": new_status, "project_id": project_id})

            connection.commit()

            status_messages = {
                2: ("Project approved. You are now the sole approver.", "success"),
                1: ("Project status set to 'Pending'. You are now linked to it.", "info"),
                0: ("Project has been unlisted.", "warning")
            }
            message, category = status_messages.get(new_status)
            flash(message, category)

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
                    u.name, u.role,
                    COUNT(t.id) AS team_count
                FROM projects p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN teams t ON p.id = t.project_id
                WHERE p.user_id = :user_id
                GROUP BY p.id, u.email, u.role
                ORDER BY p.id DESC
            """)
            projects = connection.execute(project_query, {"user_id": user_id}).mappings().all()
            return projects

    except Exception as e:
        print(f"Database error fetching user projects: {e}")
        return []

def get_all_projects(engine, session, page=1, per_page=12):
    try:
        offset = (page - 1) * per_page
        user_role = session.get('role')
        user_id = session.get('user_id')
        
        query_text = ""
        params = {}

        if user_role == 3:
            with engine.connect() as conn:
                instructor_query = text("SELECT instructor_id FROM users WHERE id = :user_id")
                result = conn.execute(instructor_query, {"user_id": user_id}).first()
                
                if not result or not result.instructor_id:
                    return []
                
                instructor_id = result.instructor_id

            query_text = """
                SELECT p.id, p.name, p.description, p.status, u.name AS business_name, u.role
                FROM projects p
                JOIN users u ON p.user_id = u.id
                JOIN instructor_projects ip ON p.id = ip.project_id
                WHERE ip.instructor_id = :instructor_id AND ip.status = 2
                ORDER BY p.id DESC
                LIMIT :per_page OFFSET :offset
            """
            params = {
                "instructor_id": instructor_id,
                "per_page": per_page,
                "offset": offset
            }
        else:
            query_text = """
                SELECT p.id, p.name, p.description, p.status, u.name AS business_name, u.role
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE p.status IN (0, 1)
                ORDER BY p.id DESC
                LIMIT :per_page OFFSET :offset
            """
            params = {
                "per_page": per_page,
                "offset": offset
            }

        with engine.connect() as connection:
            query = text(query_text)
            projects = connection.execute(query, params).mappings().all()
            return projects
            
    except Exception as e:
        print(f"Database error fetching all projects: {e}")
        return []

def load_projects_html(engine):
    page = request.args.get('page', 1, type=int)
    per_page = 12 
    projects = get_all_projects(engine, session, page=page, per_page=per_page)
    return render_template('partials/projects_list.html', projects=projects)

def check_if_user_can_edit_links(user_id, project, engine):
    """Checks if a user is the project owner or a student in an assigned team."""
    if not user_id:
        return False
    
    if user_id == project.user_id:
        return True
    
    with engine.connect() as conn:
        query = text("""
            SELECT 1 FROM team_members tm
            JOIN teams t ON tm.team_id = t.id
            WHERE tm.user_id = :user_id AND t.project_id = :project_id
            LIMIT 1
        """)
        result = conn.execute(query, {"user_id": user_id, "project_id": project.id}).first()
        return result is not None


def update_project_links(project_id, engine):
    """Updates the project and github links for a project."""
    user_id = session.get('user_id')
    project = get_project_by_id(project_id, engine)

    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

    if not check_if_user_can_edit_links(user_id, project, engine):
        flash("You do not have permission to edit these links.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    
    project_link = request.form.get('project_link', '')
    github_link = request.form.get('github_link', '')

    try:
        with engine.connect() as conn:
            query = text("UPDATE projects SET project_link = :project_link, github_link = :github_link WHERE id = :project_id")
            conn.execute(query, {
                "project_link": project_link,
                "github_link": github_link,
                "project_id": project_id
            })
            conn.commit()
        flash("Project links updated successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('project_page', project_id=project_id))

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

def update_project(project_id, request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to update a project.", "warning")
        return redirect(url_for('login'))
        
    project = get_project_by_id(project_id, engine)
    if not project or project.user_id != session['user_id']:
        flash("You do not have permission to edit this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
        
    new_name = request.form.get('name')
    new_description = request.form.get('description')
    
    if not new_name or not new_description:
        flash("Project name and description cannot be empty.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    # --- NEW LOGIC FOR APPENDING/DELETING FILES ---

    # 1. Get list of files to delete from the form
    files_to_delete = request.form.getlist('files_to_delete')
    
    # 2. Get the current list of files from the DB
    current_paths = []
    if project.attachment_path:
        current_paths = project.attachment_path.split(';')

    paths_to_keep = []
    
    # 3. Handle deletions
    if files_to_delete:
        for path in current_paths:
            if path in files_to_delete:
                # Delete the physical file
                try:
                    file_path = os.path.join('.', path.lstrip('/'))
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting old file {path}: {e}")
            else:
                # This file was not marked for deletion, so we keep it
                paths_to_keep.append(path)
    else:
        # No deletions requested, so keep all current paths
        paths_to_keep = current_paths

    # 4. Handle additions
    new_files = request.files.getlist('attachment')
    new_paths = []
    if new_files and any(f.filename for f in new_files):
        for file in new_files:
            if file and file.filename:
                try:
                    fs_save_path, url_path = _get_upload_paths(project.name, file.filename)
                    file.save(fs_save_path)
                    new_paths.append(url_path)
                except Exception as e:
                    flash(f"Error saving new file {file.filename}: {e}", "danger")
                    return redirect(url_for('project_page', project_id=project_id))

    # 5. Combine lists and save
    final_paths = paths_to_keep + new_paths
    final_attachment_path_str = ";".join(final_paths) if final_paths else None
    
    # --- END NEW LOGIC ---

    try:
        with engine.connect() as connection:
            update_query = text("""
                UPDATE projects 
                SET name = :name, description = :description, attachment_path = :attachment_path 
                WHERE id = :project_id AND user_id = :user_id
            """)
            params = {
                "name": new_name, 
                "description": new_description, 
                "attachment_path": final_attachment_path_str,
                "project_id": project_id, 
                "user_id": session['user_id']
            }
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
    if not project or project.user_id != session['user_id']:
        flash("You do not have permission to delete this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
        
    try:
        project_name = project.name 

        with engine.connect() as connection:
            delete_query = text("DELETE FROM projects WHERE id = :project_id AND user_id = :user_id")
            connection.execute(delete_query, {"project_id": project_id, "user_id": session['user_id']})
            connection.commit()

        try:
            sanitized_project_name = secure_filename(str(project_name))[:50]
            fs_upload_dir = os.path.join('.', 'uploads', sanitized_project_name)
            
            if os.path.isdir(fs_upload_dir):
                shutil.rmtree(fs_upload_dir)
                print(f"Successfully deleted directory: {fs_upload_dir}")
            else:
                print(f"Directory not found, skipping deletion: {fs_upload_dir}")
                
        except Exception as file_e:
            print(f"Error deleting project directory: {file_e}")
            flash("Project deleted, but an error occurred while cleaning up associated files.", "warning")
            return redirect(url_for('profile'))
            
        flash("Project deleted successfully.", "success")

    except Exception as db_e:
        flash(f"An error occurred while deleting the project: {db_e}", "danger")
        return redirect(url_for('project_page', project_id=project_id))
        
    return redirect(url_for('profile'))

def check_if_user_can_chat(user_id, project_id, engine):
    if not user_id:
        return False

    with engine.connect() as conn:
        owner_query = text("SELECT 1 FROM projects WHERE id = :project_id AND user_id = :user_id")
        if conn.execute(owner_query, {"project_id": project_id, "user_id": user_id}).first():
            return True

        student_member_query = text("""
            SELECT 1 FROM team_members tm
            JOIN teams t ON tm.team_id = t.id
            WHERE tm.user_id = :user_id AND t.project_id = :project_id
        """)
        if conn.execute(student_member_query, {"user_id": user_id, "project_id": project_id}).first():
            return True

        instructor_query = text("""
            SELECT 1 FROM users AS instructor
            JOIN users AS student ON instructor.id = student.instructor_id
            JOIN team_members tm ON student.id = tm.user_id
            JOIN teams t ON tm.team_id = t.id
            WHERE instructor.id = :user_id AND t.project_id = :project_id
        """)
        if conn.execute(instructor_query, {"user_id": user_id, "project_id": project_id}).first():
            return True

    return False

def check_if_user_can_comment(user_id, project, engine):
    if not user_id:
        return False

    if user_id == project.user_id:
        return True

    if session.get('role') == 0 and project.status in [1, 2]:
        return True

    with engine.connect() as conn:
        query = text("""
            SELECT 1 FROM team_members tm
            JOIN teams t ON tm.team_id = t.id
            WHERE tm.user_id = :user_id AND t.project_id = :project_id
            LIMIT 1
        """)
        result = conn.execute(query, {"user_id": user_id, "project_id": project.id}).first()
        if result:
            return True

    return False

def get_comments_for_project(project_id, engine):
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT c.id, c.comment, c.created_at, c.attachment_path,
                       u.name, u.email, u.role, c.user_id
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.project_id = :project_id
                ORDER BY c.created_at ASC
            """)
            result = conn.execute(query, {"project_id": project_id}).mappings().all()
            return result
    except Exception as e:
        print(f"Database error fetching comments: {e}")
        return []

def add_comment_to_project(project_id, request, engine):
    user_id = session.get('user_id')
    comment_text = request.form.get('comment')

    if not user_id:
        flash("You must be logged in to comment.", "warning")
        return redirect(url_for('login'))

    files = request.files.getlist('attachment')
    if not comment_text and not any(f.filename for f in files):
        flash("Comment cannot be empty.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    project = get_project_by_id(project_id, engine)
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

    if not check_if_user_can_comment(user_id, project, engine):
        flash("You do not have permission to comment on this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    attachment_paths = []
    for file in files:
        if file and file.filename:
            try:
                fs_save_path, url_path = _get_upload_paths(project.name, file.filename)
                file.save(fs_save_path)
                attachment_paths.append(url_path)
            except Exception as e:
                flash(f"Error saving file {file.filename}: {e}", "danger")
                return redirect(url_for('project_page', project_id=project_id))

    attachment_path_str = ";".join(attachment_paths) if attachment_paths else None

    try:
        with engine.connect() as conn:
            query = text("""
                INSERT INTO comments (user_id, project_id, comment, attachment_path)
                VALUES (:user_id, :project_id, :comment, :attachment_path)
            """)
            conn.execute(query, {
                "user_id": user_id,
                "project_id": project_id,
                "comment": comment_text,
                "attachment_path": attachment_path_str
            })
            conn.commit()
            flash("Comment added successfully.", "success")
    except Exception as e:
        flash(f"An error occurred while posting your comment: {e}", "danger")

    return redirect(url_for('project_page', project_id=project_id))

def delete_comment_on_project(project_id, comment_id, engine):
    """Handles deleting a comment and its associated attachment."""
    user_id = session.get('user_id')
    if not user_id:
        flash("You must be logged in to delete a comment.", "warning")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        with engine.connect() as conn:
            with conn.begin(): 
                
                query_details = text("""
                    SELECT user_id, attachment_path 
                    FROM comments 
                    WHERE id = :comment_id AND project_id = :project_id
                """)
                comment = conn.execute(query_details, {
                    "comment_id": comment_id, 
                    "project_id": project_id
                }).mappings().first()

                if not comment:
                    flash("Comment not found.", "danger")
                    return redirect(url_for('project_page', project_id=project_id))

                if comment.user_id != user_id:
                    flash("You do not have permission to delete this comment.", "danger")
                    return redirect(url_for('project_page', project_id=project_id))
                
                if comment.attachment_path:
                    paths_to_delete = comment.attachment_path.split(';')
                    for path in paths_to_delete:
                        if not path: continue
                        try:
                            file_path = os.path.join('.', path.lstrip('/'))
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            else:
                                print(f"Warning: File not found, cannot delete: {file_path}")
                        except Exception as e:
                            print(f"Error deleting file {path}: {e}")

                delete_query = text("DELETE FROM comments WHERE id = :comment_id")
                conn.execute(delete_query, {"comment_id": comment_id})
                
                flash("Comment deleted successfully.", "success")
                
    except Exception as e:
        flash(f"An error occurred while deleting the comment: {e}", "danger")

    return redirect(url_for('project_page', project_id=project_id))
