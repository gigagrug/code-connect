import os
import shutil
from sqlalchemy import text
from flask import flash, redirect, url_for, session, request, render_template, current_app
from werkzeug.utils import secure_filename
import resend

# the page showing all projects, viewable by admins

RESEND_KEY = os.environ.get('RESEND_KEY')
RESEND_EMAIL = os.environ.get('RESEND_EMAIL')

def _check_and_get_unique_path(fs_save_path):
    if not os.path.exists(fs_save_path):
        return fs_save_path, os.path.basename(fs_save_path)
    directory, filename = os.path.split(fs_save_path)
    filename_base, extension = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{filename_base}({counter}){extension}"
        new_fs_save_path = os.path.join(directory, new_filename)
        if not os.path.exists(new_fs_save_path):
            return new_fs_save_path, new_filename
        counter += 1

def _get_upload_paths(project_name, original_filename):
    sanitized_project_name = secure_filename(str(project_name))[:50]
    safe_filename = secure_filename(original_filename)
    base_upload_dir = current_app.config['UPLOAD_DIR']
    fs_upload_dir = os.path.join(base_upload_dir, sanitized_project_name)
    os.makedirs(fs_upload_dir, exist_ok=True)
    fs_save_path = os.path.join(fs_upload_dir, safe_filename)
    final_fs_save_path, final_filename = _check_and_get_unique_path(fs_save_path)
    url_path = f"/uploads/{sanitized_project_name}/{final_filename}"
    return (final_fs_save_path, url_path)

def _get_project_participants_emails(project_id, engine):
    emails = set()
    try:
        with engine.connect() as conn:
            query = text("""
                -- 1. Project Owner
                SELECT u.email
                FROM users u
                JOIN projects p ON u.id = p.user_id
                WHERE p.id = :project_id

                UNION

                -- 2. Students on Teams
                SELECT u.email
                FROM users u
                JOIN team_members tm ON u.id = tm.user_id
                JOIN teams t ON tm.team_id = t.id
                WHERE t.project_id = :project_id

                UNION

                -- 3. Instructors directly linked to the project
                SELECT u.email
                FROM users u
                JOIN instructor_projects ip ON u.id = ip.instructor_id
                WHERE ip.project_id = :project_id

                UNION

                -- 4. Instructors of the students on the teams
                SELECT i.email
                FROM users i
                JOIN users s ON i.id = s.instructor_id
                JOIN team_members tm ON s.id = tm.user_id
                JOIN teams t ON tm.team_id = t.id
                WHERE t.project_id = :project_id
            """)
            result = conn.execute(query, {"project_id": project_id}).mappings().all()
            for row in result:
                emails.add(row.email)
    except Exception as e:
        print(f"Error getting project participant emails: {e}")
    
    return emails

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
    if new_status not in [0, 1, 2, 4]:
        flash("Invalid status value. Please select a valid option.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        with engine.connect() as connection:
            with connection.begin(): # Start transaction
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
                elif new_status == 4:
                    update_students_query = text("""
                    UPDATE users u
                    JOIN team_members tm ON u.id = tm.user_id
                    JOIN teams t ON tm.team_id = t.id
                    SET u.role = 2
                    WHERE t.project_id = :project_id AND u.role = 3
                    """)
                    connection.execute(update_students_query, {"project_id": project_id})

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

            status_messages = {
                2: ("Project approved. You are now the sole approver.", "success"),
                1: ("Project status set to 'Pending'. You are now linked to it.", "info"),
                0: ("Project has been unlisted.", "warning"),
                4: ("Project marked as 'Finished'.", "success")
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

def get_all_projects(engine, session, page=1, per_page=12, search_query=None, status_filter=None, sort_order='desc'):
    try:
        offset = (page - 1) * per_page
        user_role = session.get('role')
        user_id = session.get('user_id')
        
        # --- Filter Construction ---
        where_clauses = []
        params = {
            "per_page": per_page,
            "offset": offset
        }

        if search_query:
            where_clauses.append("(p.name LIKE :search OR u.name LIKE :search)")
            params["search"] = f"%{search_query}%"

        if status_filter is not None and status_filter != '':
            # If status is "all" (or similar empty string logic in JS), we just don't add this clause
            # But if it's a specific number string:
            try:
                status_val = int(status_filter)
                where_clauses.append("p.status = :status_val")
                params["status_val"] = status_val
            except ValueError:
                pass # Ignore invalid status filters

        # --- Sorting Construction ---
        # Security: Whitelist sort direction
        direction = "ASC" if sort_order == 'asc' else "DESC"
        order_by_clause = f"ORDER BY p.id {direction}"

        if user_role == 3:
            # --- Student View (Filtered by Instructor logic) ---
            with engine.connect() as conn:
                instructor_query = text("SELECT instructor_id FROM users WHERE id = :user_id")
                result = conn.execute(instructor_query, {"user_id": user_id}).first()
                
                if not result or not result.instructor_id:
                    return []
                
                instructor_id = result.instructor_id
                params["instructor_id"] = instructor_id

            # Base Constraint: Must be approved by student's instructor
            where_clauses.append("ip.instructor_id = :instructor_id")
            where_clauses.append("ip.status = 2")

            where_str = " AND ".join(where_clauses)
            query_text = f"""
                SELECT p.id, p.name, p.description, p.status, u.name AS business_name, u.role
                FROM projects p
                JOIN users u ON p.user_id = u.id
                JOIN instructor_projects ip ON p.id = ip.project_id
                WHERE {where_str}
                {order_by_clause}
                LIMIT :per_page OFFSET :offset
            """
        else:
            # --- General View (Public / Business / Instructor Browsing) ---
            # Base Constraint: Status must be 0 or 1 (unless overridden by filter?)
            # Standard logic was "p.status IN (0, 1)".
            # If a user explicitly filters for "Finished" (4), they won't see it if we hardcode 0,1.
            # However, usually public index only shows Available (1) or Unlisted/Pending (0).
            # Let's respect the filter if provided, otherwise default to 0,1.
            
            if status_filter is not None and status_filter != '':
                 # If filtering, we trust the filter (and the WHERE logic added above)
                 # But we should likely still prevent seeing deleted stuff if that existed.
                 pass 
            else:
                 where_clauses.append("p.status IN (0, 1)")

            where_str = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            query_text = f"""
                SELECT p.id, p.name, p.description, p.status, u.name AS business_name, u.role
                FROM projects p
                JOIN users u ON p.user_id = u.id
                WHERE {where_str}
                {order_by_clause}
                LIMIT :per_page OFFSET :offset
            """

        with engine.connect() as connection:
            query = text(query_text)
            projects = connection.execute(query, params).mappings().all()
            return projects
            
    except Exception as e:
        print(f"Database error fetching all projects: {e}")
        return []

def load_projects_html(engine):
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', None)
    status = request.args.get('status', None)
    sort = request.args.get('sort', 'desc')
    
    per_page = 12 
    projects = get_all_projects(engine, session, page=page, per_page=per_page, search_query=search, status_filter=status, sort_order=sort)
    return render_template('partials/projects_list.html', projects=projects)

def check_if_user_can_edit_links(user_id, project, engine):
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
                WHERE tm.user_id = :user_id AND p.status IN (1, 2, 3, 4)
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
                members_query = text("SELECT u.name, u.email FROM team_members tm JOIN users u ON tm.user_id = u.id WHERE tm.team_id = :team_id ORDER BY u.email")
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

    files_to_delete = request.form.getlist('files_to_delete')
    
    current_paths = []
    if project.attachment_path:
        current_paths = project.attachment_path.split(';')

    paths_to_keep = []
    
    if files_to_delete:
        for path in current_paths:
            if path in files_to_delete:
                try:
                    file_path = os.path.join('.', path.lstrip('/'))
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting old file {path}: {e}")
            else:
                paths_to_keep.append(path)
    else:
        paths_to_keep = current_paths

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

    final_paths = paths_to_keep + new_paths
    final_attachment_path_str = ";".join(final_paths) if final_paths else None
    

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

    if session.get('role') == 0 and project.status in [1, 2, 3, 4]:
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

def get_comments_for_project(project_id, engine, session):
    user_id = session.get('user_id')
    user_role = session.get('role')

    if not user_id:
        return [] 

    try:
        with engine.connect() as conn:
            owner_id_query = text("SELECT user_id FROM projects WHERE id = :project_id")
            project_owner_id = conn.execute(owner_id_query, {"project_id": project_id}).scalar()

            if not project_owner_id:
                print(f"Error: Project {project_id} not found for fetching comments.")
                return []

            query_base = """
                SELECT c.id, c.comment, c.created_at, c.attachment_path,
                       u.name, u.email, u.role, c.user_id
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.project_id = :project_id
            """
            
            if user_id == project_owner_id:
                query_sql = f"{query_base} ORDER BY c.created_at ASC"
                params = {"project_id": project_id}

            elif user_role == 0:
                query_sql = f"""
                    {query_base}
                    AND (
                        c.user_id = :project_owner_id  
                        OR c.user_id = :current_user_id 
                        OR (u.role = 3 AND c.user_id IN ( 
                            SELECT tm.user_id
                            FROM team_members tm
                            JOIN teams t ON tm.team_id = t.id
                            WHERE t.project_id = :project_id
                        ))
                    )
                    ORDER BY c.created_at ASC
                """
                params = {
                    "project_id": project_id,
                    "project_owner_id": project_owner_id,
                    "current_user_id": user_id
                }

            elif user_role == 3:
                team_id_query = text("""
                    SELECT tm.team_id
                    FROM team_members tm
                    JOIN teams t ON tm.team_id = t.id
                    WHERE tm.user_id = :current_user_id AND t.project_id = :project_id
                    LIMIT 1
                """)
                team_id = conn.execute(team_id_query, {"current_user_id": user_id, "project_id": project_id}).scalar()

                instructor_id_query = text("SELECT instructor_id FROM users WHERE id = :current_user_id")
                instructor_id = conn.execute(instructor_id_query, {"current_user_id": user_id}).scalar()

                query_conditions = ["c.user_id = :project_owner_id"]
                params = {"project_id": project_id, "project_owner_id": project_owner_id, "current_user_id": user_id}

                if instructor_id:
                    query_conditions.append("c.user_id = :instructor_id")
                    params["instructor_id"] = instructor_id
                
                if team_id:
                    query_conditions.append("c.user_id IN (SELECT user_id FROM team_members WHERE team_id = :team_id)")
                    params["team_id"] = team_id
                else:
                    query_conditions.append("c.user_id = :current_user_id")

                query_sql = f"""
                    {query_base}
                    AND (
                        {' OR '.join(query_conditions)}
                    )
                    ORDER BY c.created_at ASC
                """

            else:
                return [] 

            result = conn.execute(text(query_sql), params).mappings().all()
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

    try:
        if not RESEND_KEY:
            print("Warning: RESEND_KEY not set. Skipping comment notification email.")
            return redirect(url_for('project_page', project_id=project_id))
        
        # 1. Get commenter's details
        commenter_name = ""
        commenter_email = ""
        with engine.connect() as conn:
            commenter_query = text("SELECT name, email FROM users WHERE id = :user_id")
            commenter = conn.execute(commenter_query, {"user_id": user_id}).mappings().first()
            if commenter:
                commenter_name = commenter.name if commenter.name else commenter.email
                commenter_email = commenter.email

        # 2. Get all participant emails
        recipients = _get_project_participants_emails(project_id, engine)
        
        # 3. Remove the person who just commented
        recipients.discard(commenter_email)

        if recipients:
            project_url = url_for('project_page', project_id=project_id, _external=True)
            project_name = project.name
            subject = f"New comment on project: {project_name}"
            
            # Create a nice HTML email
            html_content = f"""
            <p>Hello,</p>
            <p><strong>{commenter_name}</strong> just posted a new comment on the project: <strong>{project_name}</strong>.</p>
            <p><strong>Comment:</strong></p>
            <blockquote style="border-left: 2px solid #ccc; padding-left: 10px; margin-left: 5px; font-style: italic;">
                {comment_text}
            </blockquote>
            <p>You can view the comment and reply here:</p>
            <p><a href="{project_url}">{project_url}</a></p>
            <p>Thank you,</p>
            <p>The Project Portal</p>
            """
            
            # Send the email
            resend.api_key = RESEND_KEY
            r = resend.Emails.send({
                "from": RESEND_EMAIL,
                "to": RESEND_EMAIL, # Send to self (or a no-reply address)
                "bcc": list(recipients), # Use BCC to protect recipient privacy
                "subject": subject,
                "html": html_content
            })
            print(f"Comment notification email sent to {len(recipients)} recipients for project {project_id}.")
        
    except Exception as e:
        print(f"CRITICAL: Comment saved but email notification failed: {e}")
    return redirect(url_for('project_page', project_id=project_id))

def delete_comment_on_project(project_id, comment_id, engine):
    user_id = session.get('user_id')
    if not user_id:
        flash("You must be logged in to delete a comment.", "warning")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        with engine.connect() as conn:
            with conn.begin(): 
                
                query_details = text("""
                    SELECT 
                        c.user_id AS comment_owner_id, 
                        c.attachment_path, 
                        u.role AS comment_role,
                        p.user_id AS project_owner_id
                    FROM comments c
                    JOIN users u ON c.user_id = u.id
                    JOIN projects p ON c.project_id = p.id
                    WHERE c.id = :comment_id AND c.project_id = :project_id
                """)
                comment = conn.execute(query_details, {
                    "comment_id": comment_id, 
                    "project_id": project_id
                }).mappings().first()

                if not comment:
                    flash("Comment not found.", "danger")
                    return redirect(url_for('project_page', project_id=project_id))

                is_my_comment = (comment.comment_owner_id == user_id)
                is_instructor = (session.get('role') == 0)
                is_student_comment = (comment.comment_role == 3)
                is_owner_comment = (comment.comment_role == 1) 

                if not is_my_comment and not (is_instructor and (is_student_comment or is_owner_comment)):
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

def instructor_manage_files(project_id, request, engine):
    if 'user_id' not in session or session.get('role') != 0:
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    project = get_project_by_id(project_id, engine)
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('index'))

    if not (session.get('role') == 0 and project.status in [2, 3, 4]):
        flash("You can only manage files for approved or taken projects.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        files_to_delete = request.form.getlist('files_to_delete')
        
        current_paths = []
        if project.attachment_path:
            current_paths = project.attachment_path.split(';')

        paths_to_keep = []
        
        if files_to_delete:
            for path in current_paths:
                if path in files_to_delete:
                    try:
                        file_path = os.path.join('.', path.lstrip('/'))
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Error deleting old file {path}: {e}")
                else:
                    paths_to_keep.append(path)
        else:
            paths_to_keep = current_paths

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

        final_paths = paths_to_keep + new_paths
        final_attachment_path_str = ";".join(final_paths) if final_paths else None

        with engine.connect() as connection:
            update_query = text("UPDATE projects SET attachment_path = :attachment_path WHERE id = :project_id")
            params = {
                "attachment_path": final_attachment_path_str,
                "project_id": project_id
            }
            connection.execute(update_query, params)
            connection.commit()
            flash("Project files updated successfully!", "success")

    except Exception as e:
        flash(f"An error occurred while updating files: {e}", "danger")
        
    return redirect(url_for('project_page', project_id=project_id))

def rename_project_attachment(project_id, request, engine):
    if 'user_id' not in session:
        flash("You must be logged in.", "danger")
        return redirect(url_for('project_page', project_id=project_id))
    
    user_id = session.get('user_id')
    project = get_project_by_id(project_id, engine)

    is_owner = (project.user_id == user_id)
    is_instructor = (session.get('role') == 0)
    
    if not (is_owner or (is_instructor and project.status in [2, 3, 4])):
        flash("You do not have permission to rename files for this project.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    old_path = request.form.get('old_path')
    new_filename = request.form.get('new_filename')

    if not old_path or not new_filename:
        flash("Invalid rename request.", "danger")
        return redirect(url_for('project_page', project_id=project_id))

    try:
        original_extension = os.path.splitext(old_path)[1]
        new_filename_base = os.path.splitext(new_filename)[0]
        safe_new_filename = secure_filename(f"{new_filename_base}{original_extension}")

        if not safe_new_filename:
            flash("Invalid new filename.", "danger")
            return redirect(url_for('project_page', project_id=project_id))

        sanitized_project_name = secure_filename(str(project.name))[:50]
        upload_dir = os.path.join('.', 'uploads', sanitized_project_name)
        old_fs_path = os.path.join('.', old_path.lstrip('/'))
        
        new_fs_path_base = os.path.join(upload_dir, safe_new_filename)
        final_fs_path, final_filename = _check_and_get_unique_path(new_fs_path_base)
        new_url_path = f"/uploads/{sanitized_project_name}/{final_filename}"
        
        if os.path.exists(old_fs_path):
            os.rename(old_fs_path, final_fs_path)
        else:
            flash("File not found. Cannot rename.", "danger")
            return redirect(url_for('project_page', project_id=project_id))
            
        with engine.connect() as conn:
            current_paths = project.attachment_path.split(';')
            new_paths_list = [new_url_path if p == old_path else p for p in current_paths]
            new_paths_string = ";".join(new_paths_list)
            
            update_query = text("UPDATE projects SET attachment_path = :attachment_path WHERE id = :project_id")
            conn.execute(update_query, {"attachment_path": new_paths_string, "project_id": project_id})
            conn.commit()
            
        flash(f"File renamed to {final_filename} successfully!", "success")
    
    except Exception as e:
        print(f"Error renaming file: {e}")
        flash("An error occurred while renaming the file.", "danger")
        
    return redirect(url_for('project_page', project_id=project_id))
