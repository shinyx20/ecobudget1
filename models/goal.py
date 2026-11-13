from database import get_db


def _with_percent(row):
    d = dict(row)
    d["percent"] = (
        min(100, round(d["saved_amount"] / d["target_amount"] * 100))
        if d["target_amount"] else 0
    )
    return d


def list_goals(user_id, limit=None):
    sql = (
        "SELECT id, name, target_amount, saved_amount, deadline, description "
        "FROM savings_goals WHERE user_id = ? ORDER BY id DESC"
    )
    params = [user_id]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return [_with_percent(r) for r in get_db().execute(sql, params).fetchall()]


def get_goal(user_id, goal_id):
    row = get_db().execute(
        "SELECT id, name, target_amount, saved_amount, deadline, description "
        "FROM savings_goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id),
    ).fetchone()
    return _with_percent(row) if row else None


def count(user_id):
    return get_db().execute(
        "SELECT COUNT(*) FROM savings_goals WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def create(user_id, name, target, saved, deadline, description, today):
    db = get_db()
    cur = db.execute(
        "INSERT INTO savings_goals (user_id, name, target_amount, saved_amount, deadline, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, target, saved, deadline, description),
    )
    goal_id = cur.lastrowid
    if saved > 0:  # le montant de départ compte comme premier versement
        db.execute(
            "INSERT INTO savings_contributions (goal_id, amount, date) VALUES (?, ?, ?)",
            (goal_id, saved, today),
        )
    db.commit()
    return goal_id


def update(user_id, goal_id, name, target, deadline, description):
    db = get_db()
    cur = db.execute(
        "UPDATE savings_goals SET name = ?, target_amount = ?, deadline = ?, description = ? "
        "WHERE id = ? AND user_id = ?",
        (name, target, deadline, description, goal_id, user_id),
    )
    db.commit()
    return cur.rowcount > 0


def delete(user_id, goal_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM savings_goals WHERE id = ? AND user_id = ?", (goal_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0


def contribute(user_id, goal_id, amount, today):
    """Ajoute un versement. Retourne False si l'objectif n'appartient pas à l'utilisateur."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM savings_goals WHERE id = ? AND user_id = ?", (goal_id, user_id)
    ).fetchone()
    if not row:
        return False
    db.execute(
        "INSERT INTO savings_contributions (goal_id, amount, date) VALUES (?, ?, ?)",
        (goal_id, amount, today),
    )
    db.execute(
        "UPDATE savings_goals SET saved_amount = ROUND((saved_amount + ?)::numeric, 2)::float8 "        "WHERE id = ? AND user_id = ?",
        (amount, goal_id, user_id),
    )
    db.commit()
    return True


# ---------- Pour les statistiques ----------
def contributions_by_bucket(user_id, start, end, length):
    """Versements groupés par jour (length=10) ou par mois (length=7)."""
    # `length` est un entier interne (jamais une saisie utilisateur)
    rows = get_db().execute(
        f"SELECT substr(sc.date, 1, {int(length)}) AS bucket, SUM(sc.amount) AS total "
        "FROM savings_contributions sc JOIN savings_goals g ON g.id = sc.goal_id "
        "WHERE g.user_id = ? AND sc.date >= ? AND sc.date <= ? GROUP BY bucket",
        (user_id, start, end),
    ).fetchall()
    return {r["bucket"]: r["total"] for r in rows}


def contributions_before(user_id, start):
    return get_db().execute(
        "SELECT COALESCE(SUM(sc.amount), 0) FROM savings_contributions sc "
        "JOIN savings_goals g ON g.id = sc.goal_id WHERE g.user_id = ? AND sc.date < ?",
        (user_id, start),
    ).fetchone()[0]