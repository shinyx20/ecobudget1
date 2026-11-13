from database import get_db


# ---------- Catégories ----------
def get_categories():
    """Catégories prédéfinies (dépenses puis revenus)."""
    rows = get_db().execute(
        "SELECT id, name, type, icon FROM categories "
        "WHERE user_id IS NULL ORDER BY type ASC, id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_category(category_id):
    return get_db().execute(
        "SELECT id, name, type, icon FROM categories "
        "WHERE id = ? AND user_id IS NULL",
        (category_id,),
    ).fetchone()


# ---------- Transactions ----------
def count_all(user_id):
    return get_db().execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def list_transactions(user_id, q="", type_="", category_id=None,
                      date_from="", date_to=""):
    """Liste filtrée. Toutes les valeurs passent par des paramètres (?)."""
    sql = (
        "SELECT t.id, t.type, t.amount, t.description, t.date, t.category_id, "
        "       c.name AS category_name, c.icon AS category_icon "
        "FROM transactions t "
        "JOIN categories c ON c.id = t.category_id "
        "WHERE t.user_id = ?"
    )
    params = [user_id]

    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " AND (t.description LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')"
        params += [like, like]
    if type_:
        sql += " AND t.type = ?"
        params.append(type_)
    if category_id:
        sql += " AND t.category_id = ?"
        params.append(category_id)
    if date_from:
        sql += " AND t.date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND t.date <= ?"
        params.append(date_to)

    sql += " ORDER BY t.date DESC, t.id DESC"
    return get_db().execute(sql, params).fetchall()


def create(user_id, category_id, type_, amount, description, date):
    db = get_db()
    cur = db.execute(
        "INSERT INTO transactions (user_id, category_id, type, amount, description, date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, category_id, type_, amount, description, date),
    )
    db.commit()
    return cur.lastrowid


def update(user_id, tx_id, category_id, type_, amount, description, date):
    """Retourne True si une ligne a été modifiée (et seulement si elle appartient à user_id)."""
    db = get_db()
    cur = db.execute(
        "UPDATE transactions SET category_id = ?, type = ?, amount = ?, "
        "description = ?, date = ? WHERE id = ? AND user_id = ?",
        (category_id, type_, amount, description, date, tx_id, user_id),
    )
    db.commit()
    return cur.rowcount > 0


def delete(user_id, tx_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0


# ---------- Calculs pour le dashboard ----------
def total_balance(user_id):
    """Solde total = tous les revenus - toutes les dépenses."""
    row = get_db().execute(
        "SELECT COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0) "
        "FROM transactions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return row[0]


def month_totals(user_id, month):
    """Retourne (revenus, dépenses) du mois 'YYYY-MM'."""
    rows = get_db().execute(
        "SELECT type, COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE user_id = ? AND substr(date, 1, 7) = ? GROUP BY type",
        (user_id, month),
    ).fetchall()
    totals = {"income": 0.0, "expense": 0.0}
    for r in rows:
        totals[r["type"]] = r["total"]
    return totals["income"], totals["expense"]


def expenses_by_category(user_id, month):
    rows = get_db().execute(
        "SELECT c.name, c.icon, SUM(t.amount) AS total "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.user_id = ? AND t.type = 'expense' AND substr(t.date, 1, 7) = ? "
        "GROUP BY c.id ORDER BY total DESC",
        (user_id, month),
    ).fetchall()
    return [dict(r) for r in rows]


def monthly_totals(user_id, start_month):
    """{'2026-11': {'income': x, 'expense': y}, ...} à partir de start_month."""
    rows = get_db().execute(
        "SELECT substr(date, 1, 7) AS month, type, SUM(amount) AS total "
        "FROM transactions WHERE user_id = ? AND substr(date, 1, 7) >= ? "
        "GROUP BY month, type",
        (user_id, start_month),
    ).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r["month"], {"income": 0.0, "expense": 0.0})[r["type"]] = r["total"]
    return result


def recent(user_id, limit=5):
    return get_db().execute(
        "SELECT t.id, t.type, t.amount, t.description, t.date, "
        "       c.name AS category_name, c.icon AS category_icon "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.user_id = ? ORDER BY t.date DESC, t.id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()



# ---------- Pour les statistiques ----------
def range_expenses_by_category(user_id, start, end):
    rows = get_db().execute(
        "SELECT c.name, c.icon, SUM(t.amount) AS total "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.user_id = ? AND t.type = 'expense' AND t.date >= ? AND t.date <= ? "
        "GROUP BY c.id ORDER BY total DESC",
        (user_id, start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def range_bucket_totals(user_id, start, end, length):
    """{'2026-11-05': {'income': x, 'expense': y}, ...} par jour (10) ou par mois (7)."""
    # `length` est un entier interne (jamais une saisie utilisateur)
    rows = get_db().execute(
        f"SELECT substr(date, 1, {int(length)}) AS bucket, type, SUM(amount) AS total "
        "FROM transactions WHERE user_id = ? AND date >= ? AND date <= ? "
        "GROUP BY bucket, type",
        (user_id, start, end),
    ).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r["bucket"], {"income": 0.0, "expense": 0.0})[r["type"]] = r["total"]
    return result