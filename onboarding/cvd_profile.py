"""User-entered diagnoses; separate from preference ratings and scoring."""
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from preference.models import validate_key
from preference.storage import DATABASE

# Ordinal encoding, not a clinical measurement or a 0–1 simulation strength.
SEVERITY_LEVELS = {'mild': 1, 'moderate': 2, 'severe': 3}


def _connect(database):
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('''CREATE TABLE IF NOT EXISTS cvd_profiles (
        user_id TEXT PRIMARY KEY, type TEXT NOT NULL, severity TEXT NOT NULL,
        source TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    return connection


def get_cvd_profile(user_id, database=DATABASE):
    validate_key(user_id, 'user_id')
    connection = _connect(database)
    try:
        row = connection.execute('SELECT * FROM cvd_profiles WHERE user_id=?', (user_id,)).fetchone()
        if row is None:
            return None
        profile = dict(row)
        profile['severity_level'] = SEVERITY_LEVELS[profile['severity']]
        return profile
    finally:
        connection.close()


def save_cvd_profile(user_id, cvd_type, severity, database=DATABASE):
    validate_key(user_id, 'user_id')
    if cvd_type not in ('deutan', 'protan', 'tritan', 'other'):
        raise ValueError('Select the type from your diagnosis. Unsure is not supported yet.')
    if severity not in SEVERITY_LEVELS:
        raise ValueError('Select the severity from your diagnosis. Unsure is not supported yet.')
    connection = _connect(database)
    try:
        with connection:
            connection.execute('''INSERT INTO cvd_profiles VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET type=excluded.type,
                severity=excluded.severity, source=excluded.source, updated_at=excluded.updated_at''',
                (user_id, cvd_type, severity, 'user_entered_diagnosis', datetime.now(timezone.utc).isoformat()))
    finally:
        connection.close()
    return get_cvd_profile(user_id, database)
