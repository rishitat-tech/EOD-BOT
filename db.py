import sqlite3
from datetime import datetime

DB_NAME = "eod_bot.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eod_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slack_user_id TEXT NOT NULL,
        user_name TEXT,
        date TEXT NOT NULL,
        completed_today TEXT,
        plan_tomorrow TEXT,
        has_blocker TEXT,
        blocker_details TEXT,
        help_needed TEXT,
        status TEXT,
        submitted_at TEXT,
        UNIQUE(slack_user_id, date)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slack_user_id TEXT NOT NULL UNIQUE,
        user_name TEXT,
        active INTEGER DEFAULT 1
    )
    """)

    conn.commit()
    conn.close()


def upsert_team_member(slack_user_id, user_name, active=1):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO team_members (slack_user_id, user_name, active)
    VALUES (?, ?, ?)
    ON CONFLICT(slack_user_id)
    DO UPDATE SET
        user_name = excluded.user_name,
        active = excluded.active
    """, (slack_user_id, user_name, active))

    conn.commit()
    conn.close()


def replace_active_team_members(members):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE team_members SET active = 0")

    for member in members:
        cursor.execute("""
        INSERT INTO team_members (slack_user_id, user_name, active)
        VALUES (?, ?, 1)
        ON CONFLICT(slack_user_id)
        DO UPDATE SET
            user_name = excluded.user_name,
            active = 1
        """, (
            member["slack_user_id"],
            member["user_name"]
        ))

    conn.commit()
    conn.close()


def save_eod_update(
    slack_user_id,
    user_name,
    date,
    completed_today,
    plan_tomorrow,
    has_blocker,
    blocker_details,
    help_needed,
    status
):
    conn = get_connection()
    cursor = conn.cursor()

    submitted_at = datetime.now().isoformat(timespec="seconds")

    cursor.execute("""
    INSERT INTO eod_updates (
        slack_user_id,
        user_name,
        date,
        completed_today,
        plan_tomorrow,
        has_blocker,
        blocker_details,
        help_needed,
        status,
        submitted_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(slack_user_id, date)
    DO UPDATE SET
        user_name = excluded.user_name,
        completed_today = excluded.completed_today,
        plan_tomorrow = excluded.plan_tomorrow,
        has_blocker = excluded.has_blocker,
        blocker_details = excluded.blocker_details,
        help_needed = excluded.help_needed,
        status = excluded.status,
        submitted_at = excluded.submitted_at
    """, (
        slack_user_id,
        user_name,
        date,
        completed_today,
        plan_tomorrow,
        has_blocker,
        blocker_details,
        help_needed,
        status,
        submitted_at
    ))

    conn.commit()
    conn.close()


def get_updates_by_date(date):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        slack_user_id,
        user_name,
        completed_today,
        plan_tomorrow,
        has_blocker,
        blocker_details,
        help_needed,
        status,
        submitted_at
    FROM eod_updates
    WHERE date = ?
    ORDER BY user_name
    """, (date,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_active_team_members():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT slack_user_id, user_name
    FROM team_members
    WHERE active = 1
    ORDER BY user_name
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows
