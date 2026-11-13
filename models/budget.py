import re
from database import get_db

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def valid_month(value):
    return bool(value and MONTH_RE.match(value))


def shift_month(month, delta):
    """shift_month('2026-01', -1) -> '2025-12'"""
    year, m = int(month[:4]), int(month[5:7]) + delta
    while m > 12:
        m -= 12
        year += 1
    while m < 1:
        m += 12
        year -= 1
    return f"{year}-{m:02d}"


def _state(spent, budget):
    if spent > budget:
        return "danger"      # dépassé
    if spent >= 0.8 * budget:
        return "warning"     # 80 % atteint
    return "ok"


def _build(row_id, budget, spent):
    return {
        "id": row_id,
        "budget": budget,
        "spent": spent,
        "remaining": budget - spent,
        "percent": round(spent / budget * 100) if budget else 0,
        "state": _state(spent, budget),
    }


def global_status(user_id, month):
    """Budget global du mois + montant dépensé, ou None s'il n'est pas défini."""
    db = get_db()
    row = db.execute(
        "SELECT id, amount FROM budgets "
        "WHERE user_id = ? AND month = ? AND category_id IS NULL",
        (user_id, month),
    ).fetchone()
    if not row:
        return None
    spent = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE user_id = ? AND type = 'expense' AND substr(date, 1, 7) = ?",
        (user_id, month),
    ).fetchone()[0]
    return _build(row["id"], row["amount"], spent)


def get_global(user_id, month):
    """Montant du budget global (utilisé par le dashboard)."""
    status = global_status(user_id, month)
    return status["budget"] if status else None


def category_status(user_id, month):
    """Budgets par catégorie avec le montant déjà dépensé ce mois-ci."""
    rows = get_db().execute(
        "SELECT b.id, b.category_id, b.amount AS budget, c.name, c.icon, "
        "  COALESCE((SELECT SUM(t.amount) FROM transactions t "
        "            WHERE t.user_id = b.user_id AND t.category_id = b.category_id "
        "              AND t.type = 'expense' AND substr(t.date, 1, 7) = b.month), 0) AS spent "
        "FROM budgets b JOIN categories c ON c.id = b.category_id "
        "WHERE b.user_id = ? AND b.month = ? AND b.category_id IS NOT NULL "
        "ORDER BY c.name",
        (user_id, month),
    ).fetchall()
    result = []
    for r in rows:
        d = _build(r["id"], r["budget"], r["spent"])
        d.update(category_id=r["category_id"], name=r["name"], icon=r["icon"])
        result.append(d)
    return result


def count_for_month(user_id, month):
    return get_db().execute(
        "SELECT COUNT(*) FROM budgets WHERE user_id = ? AND month = ?",
        (user_id, month),
    ).fetchone()[0]


def save(user_id, month, category_id, amount):
    """Crée ou met à jour le budget (category_id = None pour le budget global)."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM budgets WHERE user_id = ? AND month = ? AND category_id IS NOT DISTINCT FROM ?",        (user_id, month, category_id),
    ).fetchone()
    if row:
        db.execute(
            "UPDATE budgets SET amount = ? WHERE id = ? AND user_id = ?",
            (amount, row["id"], user_id),
        )
    else:
        db.execute(
            "INSERT INTO budgets (user_id, category_id, month, amount) VALUES (?, ?, ?, ?)",
            (user_id, category_id, month, amount),
        )
    db.commit()


def delete(user_id, budget_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM budgets WHERE id = ? AND user_id = ?", (budget_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0


def copy_from_previous(user_id, month):
    """Copie les budgets du mois précédent (sans écraser ceux déjà définis)."""
    db = get_db()
    prev = shift_month(month, -1)
    rows = db.execute(
        "SELECT category_id, amount FROM budgets WHERE user_id = ? AND month = ?",
        (user_id, prev),
    ).fetchall()
    copied = 0
    for r in rows:
        exists = db.execute(
            "SELECT 1 FROM budgets WHERE user_id = ? AND month = ? AND category_id IS NOT DISTINCT FROM ?",            (user_id, month, r["category_id"]),
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO budgets (user_id, category_id, month, amount) VALUES (?, ?, ?, ?)",
                (user_id, r["category_id"], month, r["amount"]),
            )
            copied += 1
    db.commit()
    return copied