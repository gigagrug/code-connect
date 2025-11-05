from sqlalchemy import text
from flask import flash, redirect, url_for, session, request, render_template

def create_job(request, engine):
    if 'user_id' not in session:
        flash("You must be logged in to post a job.", "warning")
        return redirect(url_for('login'))

    if session.get('role') != 1:
        flash("Only Business users can create jobs.", "danger")
        return redirect(url_for('profile'))

    title = request.form.get('title')
    description = request.form.get('description')
    user_id = session['user_id']

    if not title or not description:
        flash("Job title and description are required.", "danger")
        return redirect(url_for('profile'))

    try:
        with engine.connect() as connection:
            insert_query = text(
                "INSERT INTO jobs (user_id, title, description, status) VALUES (:user_id, :title, :description, :status)"
            )
            params = {
                "user_id": user_id,
                "title": title,
                "description": description,
                "status": 0 
            }
            connection.execute(insert_query, params)
            connection.commit()
            flash("New job created successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while creating the job: {e}", "danger")

    return redirect(url_for('profile'))

def get_job_by_id(job_id, engine):
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    j.id, j.title, j.description, j.status, j.user_id,
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
    """Fetches all jobs with status 1 (Open) for the public jobs page."""
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
