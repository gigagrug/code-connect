import bcrypt
from flask import request, redirect, url_for, flash, session, jsonify
from sqlalchemy import text

def instructor_only():
    if 'account_type' not in session or session['account_type'] != 0:
        flash("You do not have permission to perform this action.", "danger")
        return False
    return True

def create_user_by_instructor(engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))

    email = request.form.get('user_email')
    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for('user_mgt'))

    default_password = "changeme"
    hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        with engine.connect() as conn:
            query = text("INSERT INTO users (email, password, account_type) VALUES (:email, :password, 3)")
            conn.execute(query, {"email": email, "password": hashed_password.decode('utf-8')})
            conn.commit()
        flash(f"User {email} created successfully with a default password.", "success")
    except Exception as e:
        flash(f"Error creating user: {e}", "danger")
    
    return redirect(url_for('user_mgt'))

def create_group(engine):
    if not instructor_only():
        return redirect(url_for('user_mgt'))

    group_name = request.form.get('group_name')
    project_id = request.form.get('project_id')
    user_id = session.get('user_id')

    if not all([group_name, project_id, user_id]):
        flash("Group Name and Project are required.", "danger")
        return redirect(url_for('user_mgt'))
    
    try:
        with engine.connect() as conn:
            # Begin a transaction
            with conn.begin():
                # Insert the new team
                insert_team_query = text("INSERT INTO teams (name, user_id, project_id) VALUES (:name, :user_id, :project_id)")
                conn.execute(insert_team_query, {"name": group_name, "user_id": user_id, "project_id": project_id})
                
                # Update the project's status to 2 (Taken)
                update_project_query = text("UPDATE projects SET status = 2 WHERE id = :project_id")
                conn.execute(update_project_query, {"project_id": project_id})
        
        flash("Group created and project marked as taken.", "success")
    except Exception as e:
        flash(f"Error creating group: {e}", "danger")

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
            query = text("DELETE FROM users WHERE id = :user_id AND account_type = 3")
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
            # Begin a transaction
            with conn.begin():
                # First, find the project_id associated with this team
                project_id_query = text("SELECT project_id FROM teams WHERE id = :team_id")
                result = conn.execute(project_id_query, {"team_id": team_id}).mappings().first()
                if not result:
                    flash("Team not found.", "warning")
                    return redirect(url_for('user_mgt'))
                project_id = result['project_id']

                # Delete the team
                delete_team_query = text("DELETE FROM teams WHERE id = :team_id")
                conn.execute(delete_team_query, {"team_id": team_id})

                # Check if any other teams are assigned to the same project
                count_query = text("SELECT COUNT(id) as team_count FROM teams WHERE project_id = :project_id")
                team_count_result = conn.execute(count_query, {"project_id": project_id}).mappings().first()
                
                # If this was the last team, revert project status to 1 (Approved)
                if team_count_result['team_count'] == 0:
                    update_project_query = text("UPDATE projects SET status = 1 WHERE id = :project_id")
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
