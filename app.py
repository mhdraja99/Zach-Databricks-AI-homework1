import os
from flask import Flask, render_template, jsonify, request
from databricks.sdk import WorkspaceClient

import lakebase

_w = WorkspaceClient()

app = Flask(__name__)
USERS_TABLE_NAME = 'users'
STATUS_TABLE_NAME = 'status'
TICKETS_TABLE_NAME = 'tickets'
MESSAGES_TABLE_NAME = 'ticket_messages'

def _current_user_email() -> str:
    """
    Resolve the current user's email so tickets are personalized.

    Databricks Apps inject the logged-in user's identity via the
    X-Forwarded-Email header on every request. Fall back to the Databricks
    SDK's current_user API for local development where that header isn't set.
    """
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


def ensure_tables():
    """Create the normalized database schema with users, status, tickets, and ticket_messages tables."""
    # Create users table
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {USERS_TABLE_NAME} (
            user_id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    
    # Create status table
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {STATUS_TABLE_NAME} (
            status_id SERIAL PRIMARY KEY,
            status_name VARCHAR(50) UNIQUE NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            description TEXT
        );
        """
    )
    
    # Insert default statuses if they don't exist
    lakebase.run_write(
        f"""
        INSERT INTO {STATUS_TABLE_NAME} (status_name, display_name, description)
        VALUES 
            ('open', 'Open', 'Ticket is newly created and awaiting assignment'),
            ('in_progress', 'In Progress', 'Ticket is currently being worked on'),
            ('resolved', 'Resolved', 'Issue has been resolved and awaiting confirmation'),
            ('closed', 'Closed', 'Ticket is closed and no further action needed')
        ON CONFLICT (status_name) DO NOTHING;
        """
    )
    
    # Create tickets table with foreign keys
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {TICKETS_TABLE_NAME} (
            ticket_id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            status_id INTEGER NOT NULL,
            created_by_user_id INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (status_id) REFERENCES {STATUS_TABLE_NAME}(status_id),
            FOREIGN KEY (created_by_user_id) REFERENCES {USERS_TABLE_NAME}(user_id)
        );
        """
    )
    
    # Create ticket_messages table with foreign keys
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {MESSAGES_TABLE_NAME} (
            message_id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            author_user_id INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES {TICKETS_TABLE_NAME}(ticket_id) ON DELETE CASCADE,
            FOREIGN KEY (author_user_id) REFERENCES {USERS_TABLE_NAME}(user_id)
        );
        """
    )


def get_or_create_user(email: str) -> int:
    """Get user_id for an email, creating the user if they don't exist."""
    # Try to get existing user
    result = lakebase.run_query(
        f"SELECT user_id FROM {USERS_TABLE_NAME} WHERE email = %s",
        (email,)
    )
    
    if result:
        return result[0]['user_id']
    
    # Create new user
    result = lakebase.run_write_returning(
        f"INSERT INTO {USERS_TABLE_NAME} (email) VALUES (%s) RETURNING user_id",
        (email,)
    )
    return result[0]['user_id']


def get_status_id(status_name: str) -> int:
    """Get status_id for a status name."""
    result = lakebase.run_query(
        f"SELECT status_id FROM {STATUS_TABLE_NAME} WHERE status_name = %s",
        (status_name,)
    )
    if result:
        return result[0]['status_id']
    return 1  # Default to 'open' if not found


@app.route('/')
def index():
    return render_template('index.html')


@app.route("/tickets", methods=["GET"])
def get_tickets():
    """Return all tickets with their message counts."""
    ensure_tables()
    rows = lakebase.run_query(
        f"""
        SELECT t.ticket_id, t.title, s.status_name as status, u.email as created_by, t.created_at,
               COUNT(m.message_id) as message_count
        FROM {TICKETS_TABLE_NAME} t
        JOIN {STATUS_TABLE_NAME} s ON t.status_id = s.status_id
        JOIN {USERS_TABLE_NAME} u ON t.created_by_user_id = u.user_id
        LEFT JOIN {MESSAGES_TABLE_NAME} m ON t.ticket_id = m.ticket_id
        GROUP BY t.ticket_id, t.title, s.status_name, u.email, t.created_at
        ORDER BY t.created_at DESC
        """
    )
    return jsonify(rows)


@app.route("/tickets", methods=["POST"])
def add_to_tickets():
    """Create a new support ticket."""
    ensure_tables()

    if request.is_json:
        title = request.json.get("title", "")
        status_name = request.json.get("status", "open")
    else:
        title = request.form.get("title", "")
        status_name = request.form.get("status", "open")

    title = title.strip() if isinstance(title, str) else ""
    email = _current_user_email()
    
    if not title:
        return jsonify({"error": "Title is required"}), 400

    # Get or create user
    user_id = get_or_create_user(email)
    status_id = get_status_id(status_name)

    result = lakebase.run_write_returning(
        f"""
        INSERT INTO {TICKETS_TABLE_NAME} (title, status_id, created_by_user_id)
        VALUES (%s, %s, %s)
        RETURNING ticket_id, title, status_id, created_by_user_id, created_at
        """,
        (title, status_id, user_id),
    )
    
    if result:
        # Get the full ticket info with joined data
        ticket = lakebase.run_query(
            f"""
            SELECT t.ticket_id, t.title, s.status_name as status, u.email as created_by, t.created_at
            FROM {TICKETS_TABLE_NAME} t
            JOIN {STATUS_TABLE_NAME} s ON t.status_id = s.status_id
            JOIN {USERS_TABLE_NAME} u ON t.created_by_user_id = u.user_id
            WHERE t.ticket_id = %s
            """,
            (result[0]['ticket_id'],)
        )
        return jsonify(ticket[0] if ticket else {})
    
    return jsonify({})


@app.route("/tickets/<int:ticket_id>", methods=["PATCH"])
def update_ticket_status(ticket_id):
    """Update a ticket's status."""
    ensure_tables()
    
    if request.is_json:
        status_name = request.json.get("status", "")
    else:
        status_name = request.form.get("status", "")
    
    status_name = status_name.strip() if isinstance(status_name, str) else ""
    
    if not status_name:
        return jsonify({"error": "Status is required"}), 400
    
    if status_name not in ['open', 'in_progress', 'resolved', 'closed']:
        return jsonify({"error": "Invalid status"}), 400
    
    status_id = get_status_id(status_name)
    
    result = lakebase.run_write_returning(
        f"""
        UPDATE {TICKETS_TABLE_NAME}
        SET status_id = %s
        WHERE ticket_id = %s
        RETURNING ticket_id
        """,
        (status_id, ticket_id),
    )
    
    if not result:
        return jsonify({"error": "Ticket not found"}), 404
    
    # Get the full ticket info with joined data
    ticket = lakebase.run_query(
        f"""
        SELECT t.ticket_id, t.title, s.status_name as status, u.email as created_by, t.created_at
        FROM {TICKETS_TABLE_NAME} t
        JOIN {STATUS_TABLE_NAME} s ON t.status_id = s.status_id
        JOIN {USERS_TABLE_NAME} u ON t.created_by_user_id = u.user_id
        WHERE t.ticket_id = %s
        """,
        (ticket_id,)
    )
    
    return jsonify(ticket[0] if ticket else {})


@app.route("/tickets/<int:ticket_id>/messages", methods=["GET"])
def get_ticket_messages(ticket_id):
    """Get all messages for a specific ticket."""
    ensure_tables()
    rows = lakebase.run_query(
        f"""
        SELECT m.message_id, m.ticket_id, m.message_text, u.email as author, m.created_at
        FROM {MESSAGES_TABLE_NAME} m
        JOIN {USERS_TABLE_NAME} u ON m.author_user_id = u.user_id
        WHERE m.ticket_id = %s
        ORDER BY m.created_at ASC
        """,
        (ticket_id,),
    )
    return jsonify(rows)


@app.route("/tickets/<int:ticket_id>/messages", methods=["POST"])
def add_message(ticket_id):
    """Add a message to a ticket."""
    ensure_tables()
    
    if request.is_json:
        message_text = request.json.get("message_text", "")
    else:
        message_text = request.form.get("message_text", "")
    
    message_text = message_text.strip() if isinstance(message_text, str) else ""
    email = _current_user_email()
    
    if not message_text:
        return jsonify({"error": "Message text is required"}), 400
    
    # Get or create user
    user_id = get_or_create_user(email)
    
    result = lakebase.run_write_returning(
        f"""
        INSERT INTO {MESSAGES_TABLE_NAME} (ticket_id, message_text, author_user_id)
        VALUES (%s, %s, %s)
        RETURNING message_id, ticket_id, message_text, author_user_id, created_at
        """,
        (ticket_id, message_text, user_id),
    )
    
    if result:
        # Get the full message info with joined data
        message = lakebase.run_query(
            f"""
            SELECT m.message_id, m.ticket_id, m.message_text, u.email as author, m.created_at
            FROM {MESSAGES_TABLE_NAME} m
            JOIN {USERS_TABLE_NAME} u ON m.author_user_id = u.user_id
            WHERE m.message_id = %s
            """,
            (result[0]['message_id'],)
        )
        return jsonify(message[0] if message else {})
    
    return jsonify({})

if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 8000))
    app.run(debug=True, host=host, port=port)