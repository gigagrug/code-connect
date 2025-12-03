import os
from sqlalchemy import text
from flask import flash, redirect, url_for, session, render_template, current_app
from werkzeug.utils import secure_filename

# job creation process (for businesses only)

def _get_application_upload_path(job_id, user_id, original_filename):
    safe_filename = secure_filename(original_filename)
    path_segment = f"job_{job_id}/user_{user_id}"
    base_upload_dir = current_app.config['UPLOAD_DIR']
    fs_upload_dir = os.path.join(base_upload_dir, 'applications', path_segment)
    os.makedirs(fs_upload_dir, exist_ok=True)
    fs_save_path = os.path.join(fs_upload_dir, safe_filename)
    if os.path.exists(fs_save_path):
        filename_base, extension = os.path.splitext(safe_filename)
        counter = 1
        while True:
            new_filename = f"{filename_base}({counter}){extension}"
            new_fs_save_path = os.path.join(fs_upload_dir, new_filename)
            if not os.path.exists(new_fs_save_path):
                fs_save_path = new_fs_save_path
                safe_filename = new_filename
                break
            counter += 1
    url_path = f"/uploads/applications/{path_segment}/{safe_filename}"
    return (fs_save_path, url_path)

def create_job(request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to post a job.", "warning")
        return redirect(url_for('login'))

    if session.get('role') != 1:
        flash("Only Business users can create jobs.", "danger")
        return redirect(url_for('profile'))

    title = request.form.get('title')
    description = request.form.get('description')
    link = request.form.get('link')
    user_id = session['user_id']

    if not title or not description:
        flash("Job title and description are required.", "danger")
        return redirect(url_for('business_jobs', user_id=session['user_id']))

    if link:
        link = link.strip()
        if not link.startswith('http://') and not link.startswith('https://'):
            link = 'https://' + link

    try:
        with engine.connect() as connection:
            insert_query = text(
                "INSERT INTO jobs (user_id, title, description, link, status) VALUES (:user_id, :title, :description, :link, :status)"
            )
            params = {
                "user_id": user_id,
                "title": title,
                "description": description,
                "link": link,
                "status": 0 
            }
            connection.execute(insert_query, params)
            connection.commit()
            flash("New job created successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while creating the job: {e}", "danger")

    return redirect(url_for('business_jobs', user_id=session['user_id']))

def get_job_by_id(job_id, engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    j.id, j.title, j.description, j.link, j.status, j.user_id,
                    u.name AS user_name, u.email
                FROM jobs j
                JOIN users u ON j.user_id = u.id
                WHERE j.id = :job_id
            """)
            result = connection.execute(query, {"job_id": job_id}).mappings().first()
            return result
    except Exception as e:
        print(f"Database error fetching job by ID: {e}")
        return None

def update_job(job_id, request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to update a job.", "warning")
        return redirect(url_for('login'))

    job = get_job_by_id(job_id, engine)
    if not job or job.user_id != session['user_id']:
        flash("You do not have permission to edit this job.", "danger")
        return redirect(url_for('job_page', job_id=job_id))

    new_title = request.form.get('title')
    new_description = request.form.get('description')
    new_status = request.form.get('status', type=int)

    if not new_title or not new_description:
        flash("Job title and description cannot be empty.", "danger")
        return redirect(url_for('job_page', job_id=job_id))

    if new_status not in [0, 1, 2]:
        flash("Invalid status value.", "danger")
        return redirect(url_for('job_page', job_id=job_id))

    try:
        with engine.connect() as connection:
            update_query = text(
                "UPDATE jobs SET title = :title, description = :description, status = :status WHERE id = :job_id"
            )
            params = {
                "title": new_title,
                "description": new_description,
                "status": new_status,
                "job_id": job_id
            }
            connection.execute(update_query, params)
            connection.commit()
            flash("Job updated successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while updating the job: {e}", "danger")

    return redirect(url_for('job_page', job_id=job_id))

def delete_job(job_id, engine):
    if 'user_id' not in session:
        flash("You must be logged in to delete a job.", "warning")
        return redirect(url_for('login'))

    job = get_job_by_id(job_id, engine)
    if not job or job.user_id != session['user_id']:
        flash("You do not have permission to delete this job.", "danger")
        return redirect(url_for('job_page', job_id=job_id))

    try:
        with engine.connect() as connection:
            delete_query = text("DELETE FROM jobs WHERE id = :job_id AND user_id = :user_id")
            connection.execute(delete_query, {"job_id": job_id, "user_id": session['user_id']})
            connection.commit()
            flash("Job deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('job_page', job_id=job_id))

    return redirect(url_for('business_jobs',user_id=session['user_id']))

def get_open_jobs(engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    j.id, j.title, j.description, j.status, j.user_id,
                    u.name AS user_name
                FROM jobs j
                JOIN users u ON j.user_id = u.id
                WHERE j.status = 1
                ORDER BY j.created_at DESC
            """)
            result = connection.execute(query).mappings().all()
            return result
    except Exception as e:
        print(f"Database error fetching open jobs: {e}")
        return []

def get_business_jobs_data(user_id, engine):
    try:
        with engine.connect() as conn:
            user_query = text("""
                SELECT id, name, bio
                FROM users
                WHERE id = :user_id AND role = 1
            """)
            business_user = conn.execute(user_query, {"user_id": user_id}).mappings().first()

            if not business_user:
                flash("Business profile not found.", "warning")
                return None

            jobs_query = text("""
                SELECT j.id, j.title, j.description, j.status, j.user_id, u.name AS user_name
                FROM jobs j
                JOIN users u ON j.user_id = u.id
                WHERE j.user_id = :user_id
                ORDER BY j.created_at DESC
            """)
            jobs = conn.execute(jobs_query, {"user_id": user_id}).mappings().all()

            return render_template(
                'business_jobs.html',
                business_user=business_user,
                jobs=jobs
            )
    except Exception as e:
        print(f"Error fetching business profile data: {e}")
        flash("An error occurred while trying to load the profile.", "danger")
        return None


def apply_to_job(job_id, request, engine):
    user_id = session.get('user_id')
    if not user_id:
        flash("You must be logged in.", "warning")
        return redirect(url_for('login'))

    if session.get('role') not in [2, 3]:
        flash("Only students and alumni can apply for jobs.", "danger")
        return redirect(url_for('job_page', job_id=job_id))
    
    resume_file = request.files.get('resume')
    cover_letter_file = request.files.get('cover_letter')
    resume_path = None
    cover_letter_path = None

    # Handle resume upload
    if resume_file and resume_file.filename:
        try:
            fs_save_path, url_path = _get_application_upload_path(job_id, user_id, resume_file.filename)
            resume_file.save(fs_save_path)
            resume_path = url_path
        except Exception as e:
            flash(f"Error saving resume: {e}", "danger")
            return redirect(url_for('job_page', job_id=job_id))
    
    # Handle cover letter upload
    if cover_letter_file and cover_letter_file.filename:
        try:
            fs_save_path, url_path = _get_application_upload_path(job_id, user_id, cover_letter_file.filename)
            cover_letter_file.save(fs_save_path)
            cover_letter_path = url_path
        except Exception as e:
            flash(f"Error saving cover letter: {e}", "danger")
            return redirect(url_for('job_page', job_id=job_id))

    try:
        with engine.connect() as conn:
            query = text("""
                INSERT INTO job_applications (job_id, user_id, resume_path, cover_letter_path)
                VALUES (:job_id, :user_id, :resume_path, :cover_letter_path)
            """)
            conn.execute(query, {
                "job_id": job_id,
                "user_id": user_id,
                "resume_path": resume_path,
                "cover_letter_path": cover_letter_path
            })
            conn.commit()
        flash("You have successfully applied for this job!", "success")
    except Exception as e:
        if 'unique_application' in str(e).lower():
            flash("You have already applied for this job.", "warning")
        else:
            flash(f"An error occurred while applying: {e}", "danger")
    
    return redirect(url_for('job_page', job_id=job_id))

def get_job_applications(job_id, engine):
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT a.id, a.user_id, a.resume_path, a.cover_letter_path, u.name, u.email
                FROM job_applications a
                JOIN users u ON a.user_id = u.id
                WHERE a.job_id = :job_id
            """)
            return conn.execute(query, {"job_id": job_id}).mappings().all()
    except Exception as e:
        print(f"Error fetching job applications: {e}")
        return []

def get_my_applications(user_id, engine):
    """Gets all applications submitted by the current user."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT a.id, a.job_id, j.title, u.name as business_name
                FROM job_applications a
                JOIN jobs j ON a.job_id = j.id
                JOIN users u ON j.user_id = u.id
                WHERE a.user_id = :user_id
                ORDER BY a.created_at DESC
            """)
            return conn.execute(query, {"user_id": user_id}).mappings().all()
    except Exception as e:
        print(f"Error fetching my applications: {e}")
        return []

def get_application_by_id(application_id, engine):
    """
    Gets a single application and its related job/user info.
    Crucially, this also checks if the session user has permission to view it.
    """
    user_id = session.get('user_id')
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    a.id, a.job_id, a.user_id AS applicant_id,
                    a.resume_path, a.cover_letter_path,
                    j.user_id AS job_owner_id, j.title AS job_title,
                    u_app.name AS applicant_name, u_app.email AS applicant_email,
                    u_biz.name AS business_name
                FROM job_applications a
                JOIN jobs j ON a.job_id = j.id
                JOIN users u_app ON a.user_id = u_app.id
                JOIN users u_biz ON j.user_id = u_biz.id
                WHERE a.id = :application_id
            """)
            app_data = conn.execute(query, {"application_id": application_id}).mappings().first()
            
            if not app_data:
                return None # Not found
            
            # Permission Check:
            if user_id == app_data.applicant_id or user_id == app_data.job_owner_id:
                return app_data
            else:
                return None # Permission denied
                
    except Exception as e:
        print(f"Error fetching application: {e}")
        return None

def check_if_user_can_chat_application(user_id, application_id, engine):
    if not user_id:
        return False
    
    app_data = get_application_by_id(application_id, engine) # This already checks permissions
    return app_data is not None

def get_application_chat_history(application_id, engine):
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT m.id AS message_id, u.email, m.message_text, m.timestamp, m.attachment_path
                FROM application_messages m
                JOIN users u ON m.user_id = u.id
                WHERE m.application_id = :application_id
                ORDER BY m.timestamp ASC
            """)
            return conn.execute(query, {"application_id": application_id}).mappings().all()
    except Exception as e:
        print(f"Error fetching application chat: {e}")
        return []
