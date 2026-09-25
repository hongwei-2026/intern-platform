from sqlalchemy import text, inspect
from intern_platform.db.session import engine

insp = inspect(engine)
cols = {c["name"] for c in insp.get_columns("users")}
needed = {
    "phone": "VARCHAR(32)",
    "major": "VARCHAR(128)",
    "grade": "VARCHAR(64)",
    "degree": "VARCHAR(64)",
    "homepage_url": "VARCHAR(512)",
    "contact_email": "VARCHAR(255)",
    "city": "VARCHAR(128)",
}
with engine.begin() as conn:
    for c, typ in needed.items():
        if c not in cols:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {c} {typ}"))
            print("added", c)
        else:
            print("exists", c)
    tables = set(insp.get_table_names())
    if "notifications" not in tables:
        conn.execute(
            text(
                """
        CREATE TABLE notifications (
          id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          title VARCHAR(255) NOT NULL,
          body TEXT,
          kind VARCHAR(64) NOT NULL DEFAULT 'review',
          project_id INTEGER,
          application_id INTEGER,
          is_read INTEGER NOT NULL DEFAULT 0,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(user_id) REFERENCES users(id),
          FOREIGN KEY(project_id) REFERENCES projects(id),
          FOREIGN KEY(application_id) REFERENCES applications(id)
        )
        """
            )
        )
        conn.execute(text("CREATE INDEX ix_notifications_user_id ON notifications (user_id)"))
        conn.execute(text("CREATE INDEX ix_notifications_is_read ON notifications (is_read)"))
        print("created notifications")
    else:
        print("notifications exists")
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
    )
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0005_profile_notify')"))
    print("stamped 0005")
