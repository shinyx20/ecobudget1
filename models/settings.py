from database import get_db

THEMES = ("light", "dark")
LANGUAGES = {"fr": "Français"}   # l'anglais et l'arabe viendront plus tard
CURRENCIES = {
    "DA": "Dinar algérien (DA)",
    "DZD": "Dinar algérien (DZD)",
    "EUR": "Euro (€)",
    "USD": "Dollar américain ($)",
}
DEFAULTS = {
    "theme": "light", "language": "fr", "currency": "DA",
    "notifications_enabled": 1, "compact_view": 0,
}


def get(user_id):
    row = get_db().execute(
        "SELECT theme, language, currency, notifications_enabled, compact_view "
        "FROM settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return dict(DEFAULTS)
    data = dict(row)
    if data["theme"] not in THEMES:
        data["theme"] = "light"
    if data["currency"] not in CURRENCIES:
        data["currency"] = "DA"
    return data

def _ensure_row(db, user_id):
    db.execute(
        "INSERT INTO settings (user_id) VALUES (?) ON CONFLICT (user_id) DO NOTHING",
        (user_id,),
    )


def save(user_id, theme, language, currency, notifications_enabled, compact_view):
    db = get_db()
    _ensure_row(db, user_id)
    db.execute(
        "UPDATE settings SET theme = ?, language = ?, currency = ?, "
        "notifications_enabled = ?, compact_view = ? WHERE user_id = ?",
        (theme, language, currency, int(notifications_enabled), int(compact_view), user_id),
    )
    db.commit()


def set_theme(user_id, theme):
    db = get_db()
    _ensure_row(db, user_id)
    db.execute("UPDATE settings SET theme = ? WHERE user_id = ?", (theme, user_id))
    db.commit()