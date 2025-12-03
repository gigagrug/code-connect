import bcrypt
from flask import request, redirect, url_for, flash, session, jsonify, render_template
from sqlalchemy import text

# the page that handles instructor assigning students to groups

def instructor_only():
    if 'role' not in session or session['role'] != 0:
        flash("You do not have permission to perform this action.", "danger")
        return False
    return True

def create_user_by_instructor(engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))

    email = request.form.get('user_email')
    instructor_id = session.get('user_id')

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for('user_mgt'))
    
    if not instructor_id:
        flash("Could not identify instructor. Please log in again.", "warning")
        return redirect(url_for('login'))

    default_password = "changeme"
    hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        with engine.connect() as conn:
            query = text(
                "INSERT INTO users (email, password, role, instructor_id) "
                "VALUES (:email, :password, 3, :instructor_id)"
            )
            params = {
                "email": email,
                "password": hashed_password.decode('utf-8'),
                "instructor_id": instructor_id
            }
            conn.execute(query, params)
            conn.commit()
        flash(f"Student {email} created and assigned to you successfully.", "success")
    except Exception as e:
        flash(f"Error creating user: {e}", "danger")
    
    return redirect(url_for('user_mgt'))

def create_group(engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))

    group_name = request.form.get('group_name')
    user_id = session.get('user_id')

    if not all([group_name, user_id]):
        flash("Group Name is required.", "danger")
        return redirect(url_for('user_mgt'))
    
    try:
        with engine.connect() as conn:
            insert_team_query = text("INSERT INTO teams (name, user_id) VALUES (:name, :user_id)")
            conn.execute(insert_team_query, {"name": group_name, "user_id": user_id})
            conn.commit()
        flash("Group created successfully.", "success")
    except Exception as e:
        flash(f"Error creating group: {e}", "danger")

    return redirect(url_for('user_mgt'))

def assign_project_to_group(team_id, engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))
    
    project_id = request.form.get('project_id')
    if not project_id:
        flash("No project selected.", "warning")
        return redirect(url_for('user_mgt'))

    try:
        with engine.connect() as conn:
            with conn.begin():
                old_project_query = text("SELECT project_id FROM teams WHERE id = :team_id")
                result = conn.execute(old_project_query, {"team_id": team_id}).scalar_one_or_none()

                if result:
                    update_old_project = text("UPDATE projects SET status = 2 WHERE id = :project_id")
                    conn.execute(update_old_project, {"project_id": result})

                update_team_query = text("UPDATE teams SET project_id = :project_id WHERE id = :team_id")
                conn.execute(update_team_query, {"project_id": project_id, "team_id": team_id})

                update_new_project = text("UPDATE projects SET status = 3 WHERE id = :project_id")
                conn.execute(update_new_project, {"project_id": project_id})

        flash("Project assigned to group successfully.", "success")
    except Exception as e:
        flash(f"Error assigning project: {e}", "danger")
        
    return redirect(url_for('user_mgt'))

def assign_user_to_team(engine):
    if not instructor_only():
        return jsonify({"success": False, "message": "Permission denied."}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    team_id = data.get('team_id')
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM team_members WHERE user_id = :user_id"), {"user_id": user_id})
            if team_id is not None:
                query = text("INSERT INTO team_members (team_id, user_id) VALUES (:team_id, :user_id)")
                conn.execute(query, {"team_id": team_id, "user_id": user_id})
            conn.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

def delete_user(user_id, engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))
    
    try:
        with engine.connect() as conn:
            query = text("DELETE FROM users WHERE id = :user_id AND role = 3")
            conn.execute(query, {"user_id": user_id})
            conn.commit()
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")
        
    return redirect(url_for('user_mgt'))

def delete_group(team_id, engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))

    try:
        with engine.connect() as conn:
            with conn.begin():
                project_id_query = text("SELECT project_id FROM teams WHERE id = :team_id")
                result = conn.execute(project_id_query, {"team_id": team_id}).mappings().first()
                if not result:
                    flash("Team not found.", "warning")
                    return redirect(url_for('user_mgt'))
                project_id = result['project_id']

                delete_team_query = text("DELETE FROM teams WHERE id = :team_id")
                conn.execute(delete_team_query, {"team_id": team_id})

                count_query = text("SELECT COUNT(id) as team_count FROM teams WHERE project_id = :project_id")
                team_count_result = conn.execute(count_query, {"project_id": project_id}).mappings().first()
                
                if team_count_result['team_count'] == 0:
                    update_project_query = text("UPDATE projects SET status = 2 WHERE id = :project_id")
                    conn.execute(update_project_query, {"project_id": project_id})
        
        flash("Group deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting group: {e}", "danger")
        
    return redirect(url_for('user_mgt'))

def update_group(team_id, engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))

    new_name = request.form.get('group_name')
    if not new_name:
        flash("New group name cannot be empty.", "warning")
        return redirect(url_for('user_mgt'))

    try:
        with engine.connect() as conn:
            query = text("UPDATE teams SET name = :name WHERE id = :team_id")
            conn.execute(query, {"name": new_name, "team_id": team_id})
            conn.commit()
        flash("Group name updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating group: {e}", "danger")
        
    return redirect(url_for('user_mgt'))

def get_user_mgt_data(engine):
    with engine.connect() as conn:
        instructor_id = session['user_id']

        requests_query = text("""
            SELECT r.id, u.email AS student_email
            FROM instructor_requests r JOIN users u ON r.student_id = u.id
            WHERE r.instructor_id = :instructor_id AND r.status = 0
        """)
        join_requests = conn.execute(requests_query, {"instructor_id": instructor_id}).all()

        denied_query = text("""
            SELECT r.id, u.email AS student_email
            FROM instructor_requests r JOIN users u ON r.student_id = u.id
            WHERE r.instructor_id = :instructor_id AND r.status = 2
        """)
        denied_requests = conn.execute(denied_query, {"instructor_id": instructor_id}).all()

        projects_query = text("""
            SELECT p.id, p.name 
            FROM projects p
            JOIN instructor_projects ip ON p.id = ip.project_id
            WHERE p.status = 2 AND ip.instructor_id = :instructor_id
            ORDER BY p.name
        """)
        projects = conn.execute(projects_query, {"instructor_id": instructor_id}).mappings().all()

        students_query = text("SELECT id, name, email FROM users WHERE role = 3 AND instructor_id = :instructor_id")
        all_students = conn.execute(students_query, {"instructor_id": instructor_id}).mappings().all()

        teams_query = text("""
            SELECT t.id, t.name, t.project_id, p.name AS project_name
            FROM teams t LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.user_id = :user_id
        """)
        teams = conn.execute(teams_query, {"user_id": instructor_id}).mappings().all()

        team_members_query = text("SELECT team_id, user_id FROM team_members")
        team_members_result = conn.execute(team_members_query).mappings().all()
        team_members_map = {}
        for row in team_members_result:
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
        teams_with_members=teams_with_members,
        join_requests=join_requests,
        denied_requests=denied_requests 
    )
