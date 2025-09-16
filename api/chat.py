from flask import session
from flask_socketio import emit, join_room
from sqlalchemy import text
from .projects import check_if_user_can_chat

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
        if not all([project_id, message_text, user_id, email]):
            return
        if not check_if_user_can_chat(user_id, project_id, engine):
            return

        try:
            with engine.connect() as conn:
                with conn.begin():
                    query = text("""
                        INSERT INTO chat_messages (project_id, user_id, message_text)
                        VALUES (:project_id, :user_id, :message_text)
                    """)
                    result = conn.execute(query, {
                        "project_id": project_id,
                        "user_id": user_id,
                        "message_text": message_text
                    })
                    
                    last_id = result.lastrowid
                    ts_query = text("SELECT timestamp FROM chat_messages WHERE id = :id")
                    timestamp = conn.execute(ts_query, {"id": last_id}).scalar_one()

                room = f'project-{project_id}'
                emit('message_broadcast', {
                    'message_id': last_id,
                    'email': email,
                    'message': message_text,
                    'timestamp': timestamp.strftime('%b %d, %Y %I:%M %p')
                }, to=room)
        except Exception as e:
            print(f"Error saving chat message: {e}")

    @socketio.on('delete_message')

    def on_delete_message(data):
        """User requests to delete their message."""
        message_id = data.get('message_id')
        user_id = session.get('user_id')
        if not message_id or not user_id:
            return

        try:
            with engine.connect() as conn:
                with conn.begin():
                    msg_query = text("SELECT user_id, project_id FROM chat_messages WHERE id = :id")
                    message = conn.execute(msg_query, {"id": message_id}).first()

                    if message and message.user_id == user_id:
                        # DELETE the message row from the database
                        delete_query = text("DELETE FROM chat_messages WHERE id = :id")
                        conn.execute(delete_query, {"id": message_id})

                        room = f'project-{message.project_id}'
                        emit('message_deleted', {'message_id': message_id}, to=room)
        except Exception as e:
            print(f"Error deleting message: {e}")
