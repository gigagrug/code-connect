from flask import request, redirect, url_for, flash, session
from sqlalchemy import text

def send_instructor_request(engine):
    if 'user_id' not in session or session.get('account_type') != 3:
        flash("Only students can send requests.", "danger")
        return redirect(url_for('profile'))

    student_id = session['user_id']
    instructor_id = request.form.get('instructor_id')

    if not instructor_id:
        flash("You must select an instructor.", "warning")
        return redirect(url_for('profile'))

    try:
        with engine.connect() as conn:
            user_check_query = text("SELECT instructor_id FROM users WHERE id = :student_id")
            user_result = conn.execute(user_check_query, {"student_id": student_id}).first()
            if user_result and user_result.instructor_id:
                flash("You are already assigned to an instructor.", "info")
                return redirect(url_for('profile'))

            request_check_query = text("SELECT id FROM instructor_requests WHERE student_id = :student_id AND status = 0")
            if conn.execute(request_check_query, {"student_id": student_id}).first():
                flash("You already have a pending request.", "info")
                return redirect(url_for('profile'))
            
            query = text("INSERT INTO instructor_requests (student_id, instructor_id) VALUES (:student_id, :instructor_id)")
            conn.execute(query, {"student_id": student_id, "instructor_id": instructor_id})
            conn.commit()
            flash("Your request has been sent successfully!", "success")

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('profile'))


def cancel_instructor_request(engine):
    if 'user_id' not in session or session.get('account_type') != 3:
        flash("Only students can cancel requests.", "danger")
        return redirect(url_for('profile'))

    student_id = session['user_id']
    try:
        with engine.connect() as conn:
            query = text("DELETE FROM instructor_requests WHERE student_id = :student_id AND status = 0")
            conn.execute(query, {"student_id": student_id})
            conn.commit()
            flash("Your request has been canceled.", "info")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('profile'))


def handle_instructor_request(request_id, engine):
    if 'user_id' not in session or session.get('account_type') != 0:
        flash("Only instructors can handle requests.", "danger")
        return redirect(url_for('user_mgt'))

    action = request.form.get('action')
    instructor_id = session['user_id']

    try:
        with engine.connect() as conn:
            with conn.begin(): # Start transaction
                # MODIFIED: Allow handling requests with status 0 (pending) OR 2 (denied)
                req_query = text("""
                    SELECT student_id FROM instructor_requests 
                    WHERE id = :request_id 
                    AND instructor_id = :instructor_id 
                    AND status IN (0, 2)
                """)
                req_result = conn.execute(req_query, {"request_id": request_id, "instructor_id": instructor_id}).first()

                if not req_result:
                    flash("Request not found or already handled.", "warning")
                    return redirect(url_for('user_mgt'))
                
                student_id = req_result.student_id

                if action == 'accept':
                    # 1. Update the user table to assign the student
                    update_user_query = text("UPDATE users SET instructor_id = :instructor_id WHERE id = :student_id")
                    conn.execute(update_user_query, {"instructor_id": instructor_id, "student_id": student_id})

                    # 2. Update the request status to accepted
                    update_req_query = text("UPDATE instructor_requests SET status = 1 WHERE id = :request_id")
                    conn.execute(update_req_query, {"request_id": request_id})

                    flash("Student request accepted.", "success")
                
                elif action == 'deny':
                    # Update the request status to denied
                    update_req_query = text("UPDATE instructor_requests SET status = 2 WHERE id = :request_id")
                    conn.execute(update_req_query, {"request_id": request_id})
                    flash("Student request denied.", "info")

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('user_mgt'))

def dismiss_denied_request(request_id, engine):
    """Allows an instructor to dismiss/delete a denied request."""
    if 'user_id' not in session or session.get('account_type') != 0:
        flash("Only instructors can handle requests.", "danger")
        return redirect(url_for('user_mgt'))

    instructor_id = session['user_id']
    
    try:
        with engine.connect() as conn:
            # Ensure the instructor can only delete their own denied requests
            query = text("""
                DELETE FROM instructor_requests 
                WHERE id = :request_id 
                AND instructor_id = :instructor_id 
                AND status = 2
            """)
            result = conn.execute(query, {
                "request_id": request_id, 
                "instructor_id": instructor_id
            })
            conn.commit()
            
            if result.rowcount > 0:
                flash("Denied request has been dismissed.", "info")
            else:
                flash("Request not found or permission denied.", "warning")

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('user_mgt'))
