import os
import base64
from flask import session, current_app
from flask_socketio import emit, join_room
from sqlalchemy import text
from .projects import check_if_user_can_chat, get_project_by_id, _get_upload_paths
from .job import check_if_user_can_chat_application, _get_application_upload_path

# chat log for communication between teams

def init_chat(socketio, engine):
    @socketio.on('join')
    def on_join(data):
        project_id = data.get('project_id')
        user_id = session.get('user_id')
        if not project_id or not user_id:
            return
        if check_if_user_can_chat(user_id, project_id, engine):
            room = f'project-{project_id}'
            join_room(room)

    @socketio.on('new_message')
    def on_new_message(data):
        project_id = data.get('project_id')
        message_text = data.get('message')
        user_id = session.get('user_id')
        email = session.get('email')
        
        file_data = data.get('file')
        original_filename = data.get('filename')

        if not all([project_id, user_id, email]):
            return
        # Allow message if either text OR file exists
        if not message_text and not file_data:
            return 
        if not check_if_user_can_chat(user_id, project_id, engine):
            return

        attachment_path = None

        if file_data and original_filename:
            try:
                project = get_project_by_id(project_id, engine)
                if not project:
                    return
                
                with current_app.app_context(): 
                    fs_save_path, url_path = _get_upload_paths(project.name, original_filename)
                
                # Remove header if present (e.g., "data:image/png;base64,")
                if ',' in file_data:
                    file_content = base64.b64decode(file_data.split(',')[1])
                else:
                    file_content = base64.b64decode(file_data)
                
                with open(fs_save_path, 'wb') as f:
                    f.write(file_content)
                
                attachment_path = url_path
            except Exception as e:
                print(f"Error saving chat file: {e}")

        try:
            with engine.connect() as conn:
                with conn.begin():
                    query = text("""
                        INSERT INTO chat_messages (project_id, user_id, message_text, attachment_path)
                        VALUES (:project_id, :user_id, :message_text, :attachment_path)
                    """)
                    result = conn.execute(query, {
                        "project_id": project_id,
                        "user_id": user_id,
                        "message_text": message_text,
                        "attachment_path": attachment_path
                    })
                    
                    last_id = result.lastrowid
                    ts_query = text("SELECT timestamp FROM chat_messages WHERE id = :id")
                    timestamp = conn.execute(ts_query, {"id": last_id}).scalar_one()

                room = f'project-{project_id}'
                emit('message_broadcast', {
                    'message_id': last_id,
                    'email': email,
                    'message': message_text,
                    'attachment_path': attachment_path,
                    'timestamp': timestamp.strftime('%b %d, %Y %I:%M %p')
                }, to=room)
        except Exception as e:
            print(f"Error saving chat message to DB: {e}")

    @socketio.on('delete_message')
    def on_delete_message(data):
        message_id = data.get('message_id')
        user_id = session.get('user_id')
        if not message_id or not user_id:
            return

        try:
            with engine.connect() as conn:
                with conn.begin():
                    msg_query = text("SELECT user_id, project_id, attachment_path FROM chat_messages WHERE id = :id")
                    message = conn.execute(msg_query, {"id": message_id}).first()

                    if message and message.user_id == user_id:
                        if message.attachment_path:
                            try:
                                base_upload_dir = current_app.config['UPLOAD_DIR']
                                # Extract relative path from URL
                                if '/uploads/' in message.attachment_path:
                                    relative_path = message.attachment_path.split('/uploads/', 1)[-1]
                                    file_path = os.path.join(base_upload_dir, relative_path)
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                            except Exception as e:
                                print(f"Error deleting file: {e}")
                                
                        delete_query = text("DELETE FROM chat_messages WHERE id = :id")
                        conn.execute(delete_query, {"id": message_id})

                        room = f'project-{message.project_id}'
                        emit('message_deleted', {'message_id': message_id}, to=room)
        except Exception as e:
            print(f"Error deleting message: {e}")

def init_application_chat(socketio, engine):
    @socketio.on('join_application_room')
    def on_join_application_room(data):
        application_id = data.get('application_id')
        user_id = session.get('user_id')
        if not application_id or not user_id:
            return
        
        if check_if_user_can_chat_application(user_id, application_id, engine):
            room = f'application-{application_id}'
            join_room(room)

    @socketio.on('new_application_message')
    def on_new_application_message(data):
        application_id = data.get('application_id')
        message_text = data.get('message')
        user_id = session.get('user_id')
        email = session.get('email')
        
        file_data = data.get('file')
        original_filename = data.get('filename')
        
        if not all([application_id, user_id, email]):
            return
        
        # Allow if text OR file exists
        if not message_text and not file_data:
            return

        if not check_if_user_can_chat_application(user_id, application_id, engine):
            return

        attachment_path = None 
        
        # Handle File Upload
        if file_data and original_filename:
            try:
                with current_app.app_context():
                    # Get Job ID from application to verify path structure or just store by application/user
                    # Ideally, _get_application_upload_path needs job_id. 
                    # We can fetch job_id from application_id if needed, but let's try a simpler path if that function isn't imported fully or requires args we don't have handy in `data`.
                    # Assuming _get_application_upload_path is imported from .job
                    
                    # Fetch job_id for the path structure
                    with engine.connect() as conn:
                        res = conn.execute(text("SELECT job_id FROM job_applications WHERE id = :id"), {"id": application_id}).first()
                        job_id = res.job_id if res else 0

                    fs_save_path, url_path = _get_application_upload_path(job_id, user_id, original_filename)
                    
                    if ',' in file_data:
                        file_content = base64.b64decode(file_data.split(',')[1])
                    else:
                        file_content = base64.b64decode(file_data)
                        
                    with open(fs_save_path, 'wb') as f:
                        f.write(file_content)
                    
                    attachment_path = url_path
            except Exception as e:
                print(f"Error saving application chat file: {e}")

        try:
            with engine.connect() as conn:
                with conn.begin():
                    query = text("""
                        INSERT INTO application_messages (application_id, user_id, message_text, attachment_path)
                        VALUES (:application_id, :user_id, :message_text, :attachment_path)
                    """)
                    result = conn.execute(query, {
                        "application_id": application_id,
                        "user_id": user_id,
                        "message_text": message_text,
                        "attachment_path": attachment_path
                    })
                    
                    last_id = result.lastrowid
                    ts_query = text("SELECT timestamp FROM application_messages WHERE id = :id")
                    timestamp = conn.execute(ts_query, {"id": last_id}).scalar_one()

                room = f'application-{application_id}'
                emit('application_message_broadcast', {
                    'message_id': last_id,
                    'email': email,
                    'message': message_text,
                    'attachment_path': attachment_path,
                    'timestamp': timestamp.strftime('%b %d, %Y %I:%M %p')
                }, to=room)
        except Exception as e:
            print(f"Error saving application chat message: {e}")

    @socketio.on('delete_application_message')
    def on_delete_application_message(data):
        message_id = data.get('message_id')
        user_id = session.get('user_id')
        if not message_id or not user_id:
            return

        try:
            with engine.connect() as conn:
                with conn.begin():
                    msg_query = text("SELECT user_id, application_id, attachment_path FROM application_messages WHERE id = :id")
                    message = conn.execute(msg_query, {"id": message_id}).first()

                    if message and message.user_id == user_id:
                        if message.attachment_path:
                            try:
                                base_upload_dir = current_app.config['UPLOAD_DIR']
                                if '/uploads/' in message.attachment_path:
                                    relative_path = message.attachment_path.split('/uploads/', 1)[-1]
                                    file_path = os.path.join(base_upload_dir, relative_path)
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                            except Exception as e:
                                print(f"Error deleting file: {e}")

                        delete_query = text("DELETE FROM application_messages WHERE id = :id")
                        conn.execute(delete_query, {"id": message_id})

                        room = f'application-{message.application_id}'
                        emit('application_message_deleted', {'message_id': message_id}, to=room)
        except Exception as e:
            print(f"Error deleting application message: {e}")
