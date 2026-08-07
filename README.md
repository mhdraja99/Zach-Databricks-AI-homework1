# Support Ticket System - Homework 1

A professional internal support ticket system built with Flask and Lakebase Postgres.

Running application url https://homework1-app-new-3497162221015794.aws.databricksapps.com/

The github url is https://github.com/mhdraja99/Zach-Databricks-AI-homework1/tree/main

## Features

- 🎫 Create and manage support tickets
- 💬 Add messages to tickets
- 📊 Update ticket status (Open, In Progress, Resolved, Closed)
- 👥 User authentication via Databricks (automatic email tracking)
- 🗄️ Normalized database schema with foreign key relationships
- 🔒 Secure credential management using Databricks secrets

## Database Schema

### Tables

**users**
- `user_id` (PK)
- `email` (UNIQUE)
- `created_at`

**status**
- `status_id` (PK)
- `status_name` (UNIQUE)
- `display_name`
- `description`

**tickets**
- `ticket_id` (PK)
- `title`
- `status_id` (FK → status)
- `created_by_user_id` (FK → users)
- `created_at`

**ticket_messages**
- `message_id` (PK)
- `ticket_id` (FK → tickets)
- `message_text`
- `author_user_id` (FK → users)
- `created_at`

## Setup Instructions

### 1. Set Up Secrets (One-time setup)

Run the setup script to securely store your Lakebase connection URL:

```bash
python setup_secrets.py
```

You'll be prompted to enter your Lakebase URL in this format:
```
postgresql://role:password@host/database?sslmode=require
```

### 2. Install Dependencies

The app automatically installs dependencies from `requirements.txt` during deployment:
- flask
- psycopg2-binary
- sqlalchemy
- databricks-sdk

### 3. Deploy the App

Deploy using the Databricks CLI:

```bash
databricks apps deploy homework1-app \
  --source-code-path /Workspace/Users/<your-email>/Zach-Databricks-AI-homework1
```

## Project Structure

```
Zach-Databricks-AI-homework1/
├── app.py                  # Main Flask application
├── app.yaml               # Databricks App configuration
├── lakebase.py            # Database connection utilities
├── requirements.txt       # Python dependencies
├── setup_secrets.py       # One-time secret setup script
├── templates/
│   └── index.html        # Frontend UI
└── README.md             # This file
```

## API Endpoints

### Tickets
- `GET /tickets` - List all tickets with message counts
- `POST /tickets` - Create a new ticket
- `PATCH /tickets/<id>` - Update ticket status

### Messages
- `GET /tickets/<id>/messages` - Get all messages for a ticket
- `POST /tickets/<id>/messages` - Add a message to a ticket

## Security

✅ **No hardcoded credentials** - Uses Databricks secrets  
✅ **Automatic user authentication** - Via X-Forwarded-Email header  
✅ **Foreign key constraints** - Ensures data integrity  
✅ **SQL injection prevention** - Parameterized queries throughout

## Development

### Local Testing (Optional)

For local development, set the `LAKEBASE_URL` environment variable:

```bash
export LAKEBASE_URL="postgresql://..."
python app.py
```

### Database Migrations

The app automatically creates tables on first run via `ensure_tables()`.

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: Lakebase Postgres (Databricks)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Deployment**: Databricks Apps
- **Secrets Management**: Databricks Secret Scopes

## License

MIT
