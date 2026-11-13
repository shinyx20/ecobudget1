import os

import psycopg
from flask import g

# Permet d'utiliser un fichier .env en local (inutile sur Vercel)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    photo         TEXT,
    photo_data    BYTEA,
    photo_mime    TEXT,
    created_at    TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS categories (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL,
    type    TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    icon    TEXT NOT NULL DEFAULT 'tag',
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_default_categories
    ON categories (name, type) WHERE user_id IS NULL;

CREATE TABLE IF NOT EXISTS transactions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    type        TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    amount      DOUBLE PRECISION NOT NULL CHECK (amount > 0),
    description TEXT,
    date        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions (user_id, date);

CREATE TABLE IF NOT EXISTS budgets (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    month       TEXT NOT NULL,
    amount      DOUBLE PRECISION NOT NULL CHECK (amount > 0)
);

CREATE TABLE IF NOT EXISTS savings_goals (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    target_amount DOUBLE PRECISION NOT NULL CHECK (target_amount > 0),
    saved_amount  DOUBLE PRECISION NOT NULL DEFAULT 0,
    deadline      TEXT,
    description   TEXT,
    created_at    TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS savings_contributions (
    id      SERIAL PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES savings_goals(id) ON DELETE CASCADE,
    amount  DOUBLE PRECISION NOT NULL CHECK (amount > 0),
    date    TEXT NOT NULL DEFAULT to_char(current_date, 'YYYY-MM-DD')
);

CREATE TABLE IF NOT EXISTS notifications (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message    TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'info',
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS settings (
    user_id               INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    theme                 TEXT NOT NULL DEFAULT 'light',
    language              TEXT NOT NULL DEFAULT 'fr',
    currency              TEXT NOT NULL DEFAULT 'DA',
    notifications_enabled INTEGER NOT NULL DEFAULT 1,
    compact_view          INTEGER NOT NULL DEFAULT 0
);
"""

DEFAULT_CATEGORIES = [
    # Dépenses
    ("Alimentation", "expense", "utensils"),
    ("Transport", "expense", "bus"),
    ("Études", "expense", "graduation-cap"),
    ("Santé", "expense", "heart-pulse"),
    ("Shopping", "expense", "shopping-bag"),
    ("Loisirs", "expense", "gamepad-2"),
    ("Logement", "expense", "house"),
    ("Autres", "expense", "ellipsis"),
    # Revenus
    ("Salaire", "income", "briefcase"),
    ("Bourse", "income", "award"),
    ("Freelance", "income", "laptop"),
    ("Cadeaux", "income", "gift"),
    ("Autres revenus", "income", "wallet"),
]


# ---------- Adaptateur : garde la même interface que sqlite3 ----------
class Row(dict):
    """Ligne de résultat : accès par nom (row["name"]) ET par position (row[0])."""

    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def _row_factory(cursor):
    keys = [c.name for c in cursor.description] if cursor.description else []

    def make_row(values):
        return Row(keys, values)

    return make_row


def _convert(sql):
    """Style sqlite (?) -> style PostgreSQL (%s)."""
    return sql.replace("%", "%%").replace("?", "%s")


class Result:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class Database:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        sql = _convert(sql)
        upper = sql.lstrip().upper()
        wants_id = (upper.startswith("INSERT") and "RETURNING" not in upper
                    and "INTO SETTINGS" not in upper)
        if wants_id:
            sql += " RETURNING id"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        lastrowid = None
        if wants_id:
            row = cur.fetchone()
            lastrowid = row[0] if row else None
        return Result(cur, lastrowid)

    def executemany(self, sql, seq):
        cur = self.conn.cursor()
        cur.executemany(_convert(sql), seq)
        return Result(cur)

    def executescript(self, script):
        cur = self.conn.cursor()
        for statement in script.split(";"):
            if statement.strip():
                cur.execute(statement)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def _database_url():
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL n'est pas défini. Ajoutez votre base PostgreSQL "
            "(variable d'environnement DATABASE_URL ou fichier .env)."
        )
    return url


def get_db():
    """Une connexion par requête, réutilisée tant que la requête dure."""
    if "db" not in g:
        conn = psycopg.connect(
            _database_url(),
            row_factory=_row_factory,
            connect_timeout=10,
            prepare_threshold=None,   # compatible avec le pooler de connexions (PgBouncer)
        )
        g.db = Database(conn)
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.rollback()   # annule toute transaction restée ouverte
        except Exception:
            pass
        db.close()


def init_db():
    """Crée les tables et les catégories par défaut (sans danger si déjà faits)."""
    db = get_db()
    db.executescript(SCHEMA)
    db.executemany(
        "INSERT INTO categories (name, type, icon) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
        DEFAULT_CATEGORIES,
    )
    db.commit()