import os
import uuid
import base64
from flask import session
from flask_socketio import emit, join_room
from sqlalchemy import text
from werkzeug.utils import secure_filename
from .projects import check_if_user_can_chat, get_project_by_id

def _get_upload_paths(project_name, original_filename):
    sanitized_project_name = secure_filename(str(project_name))[:50]
    safe_filename = secure_filename(original_filename)
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    
    fs_upload_dir = os.path.join('.', 'uploads', sanitized_project_name)
    os.makedirs(fs_upload_dir, exist_ok=True)
    
    fs_save_path = os.path.join(fs_upload_dir, unique_filename)
    url_path = f"/uploads/{sanitized_project_name}/{unique_filename}"
    
    return (fs_save_path, url_path)


def init_chat(socketio, engine):
    """Initializes all Socket.IO chat event handlers."""

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
        if not message_text and not file_data:
            return # Ignore empty submissions
        if not check_if_user_can_chat(user_id, project_id, engine):
            return

        attachment_path = None

        if file_data and original_filename:
            try:
                project = get_project_by_id(project_id, engine)
                if not project:
                    print(f"Chat Error: Project not found for ID {project_id}")
                    return

                fs_save_path, url_path = _get_upload_paths(project.name, original_filename)
                
                # Decode the Base64 string
                # It's usually "data:image/png;base64,iVBORw..." we split on the comma
                file_content = base64.b64decode(file_data.split(',')[1])
                
                with open(fs_save_path, 'wb') as f:
                    f.write(file_content)
                
                attachment_path = url_path
            except Exception as e:
                print(f"Error saving chat file: {e}")
                # Don't stop, just don't attach the file

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
                        
                        # --- ADDED FILE DELETION LOGIC ---
                        if message.attachment_path:
                            try:
                                # Convert URL path (/uploads/...) to a relative file path (./uploads/...)
                                file_path = os.path.join('.', message.attachment_path.lstrip('/'))
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                else:
                                    print(f"Warning: File not found, cannot delete: {file_path}")
                            except Exception as e:
                                # Log error but don't stop the message deletion
                                print(f"Error deleting file {message.attachment_path}: {e}")
                        # --- END FILE DELETION LOGIC ---
                                
                        delete_query = text("DELETE FROM chat_messages WHERE id = :id")
                        conn.execute(delete_query, {"id": message_id})

                        room = f'project-{message.project_id}'
                        emit('message_deleted', {'message_id': message_id}, to=room)
        except Exception as e:
            print(f"Error deleting message: {e}")
