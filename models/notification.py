from database import get_db
from models import budget as budget_model

MONTHS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def month_label(month):
    """'2026-11' -> 'novembre 2026'"""
    return f"{MONTHS_LONG[int(month[5:7]) - 1]} {month[:4]}"


def notifications_enabled(user_id):
    row = get_db().execute(
        "SELECT notifications_enabled FROM settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    return True if row is None else bool(row["notifications_enabled"])


def create(user_id, message, type_="info"):
    """Crée une notification, sauf si la même existe déjà (anti-doublon).
    Retourne True si elle a été créée."""
    if not notifications_enabled(user_id):
        return False
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM notifications WHERE user_id = ? AND message = ?",
        (user_id, message),
    ).fetchone()
    if exists:
        return False
    db.execute(
        "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
        (user_id, message, type_),
    )
    db.commit()
    return True


def check_budget_alerts(user_id, month):
    """Vérifie tous les budgets du mois. Retourne la liste des NOUVELLES alertes
    créées : [(message, 'warning' | 'danger'), ...]."""
    label = month_label(month)
    items = []
    g = budget_model.global_status(user_id, month)
    if g:
        items.append(("Budget global", g))
    for c in budget_model.category_status(user_id, month):
        items.append((f"Budget « {c['name']} »", c))

    created = []
    for name, b in items:
        if b["state"] == "danger":
            message, level = f"{name} dépassé en {label}.", "danger"
        elif b["state"] == "warning":
            message, level = f"{name} : 80 % du budget atteint en {label}.", "warning"
        else:
            continue
        if create(user_id, message, level):
            created.append((message, level))
    return created


def list_all(user_id, limit=100):
    return get_db().execute(
        "SELECT id, message, type, is_read, created_at FROM notifications "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def mark_all_read(user_id):
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    db.commit()


def delete_all(user_id):
    db = get_db()
    db.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    db.commit()