"""One-time setup script: creates the Databricks secret scope and stores the
Lakebase connection URL securely.

Run this once from a notebook or locally (with the Databricks CLI configured)
to set up your secrets. Never commit the resulting secret value anywhere.

Usage:
    Run in a Databricks notebook or:
    python setup_secrets.py
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

w = WorkspaceClient()

print("Setting up Databricks secrets for homework1-app...\n")

# Create the database secret scope
try:
    w.secrets.create_scope(scope="database")
    print("✓ Created 'database' secret scope")
except Exception as e:
    if "already exists" in str(e).lower():
        print("ℹ 'database' secret scope already exists")
    else:
        raise

# Store the Lakebase URL
print("\nPaste your Lakebase connection URL")
print("Format: postgresql://role:password@host/database?sslmode=require")
lakebase_url = getpass.getpass("Lakebase URL: ")

w.secrets.put_secret(
    scope="database",
    key="lakebase-url",
    string_value=lakebase_url
)
print("✓ Stored lakebase-url secret")

# Grant read access to all users
w.secrets.put_acl(
    scope="database",
    principal="users",
    permission=workspace.AclPermission.READ,
)
print("✓ Granted READ permission to all users")

print("\n✅ Secret setup complete!")
print("\nYour app will now read the Lakebase URL from: dbutils.secrets.get('database', 'lakebase-url')")
##