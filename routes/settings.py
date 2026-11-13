import json
from datetime import datetime

from flask import (Blueprint, Response, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash

from database import get_db
from models import settings as settings_model
from models import user as user_model
from routes.auth import login_required

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@login_required
def index():
    return render_template(
        "settings.html",
        s=settings_model.get(session["user_id"]),
        currency_options=list(settings_model.CURRENCIES.items()),
    )


@settings_bp.route("/settings/save", methods=["POST"])
@login_required
def save():
    theme = request.form.get("theme", "")
    language = request.form.get("language", "")
    currency = request.form.get("currency", "")
    notifications = request.form.get("notifications") == "on"
    compact = request.form.get("compact") == "on"

    if (theme not in settings_model.THEMES
            or language not in settings_model.LANGUAGES
            or currency not in settings_model.CURRENCIES):
        flash("Valeur invalide : les paramètres n'ont pas été enregistrés.", "error")
        return redirect(url_for("settings.index"))

    settings_model.save(session["user_id"], theme, language, currency, notifications, compact)
    flash("Paramètres enregistrés.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/settings/theme", methods=["POST"])
@login_required
def theme():
    """Appelé par le bouton lune/soleil de la barre du haut."""
    data = request.get_json(silent=True) or {}
    value = data.get("theme")
    if value not in settings_model.THEMES:
        return jsonify(ok=False), 400
    settings_model.set_theme(session["user_id"], value)
    return jsonify(ok=True)


@settings_bp.route("/settings/export")
@login_required
def export():
    """Télécharge toutes les données de l'utilisateur (JSON)."""
    uid = session["user_id"]
    db = get_db()

    def rows(sql):
        return [dict(r) for r in db.execute(sql, (uid,)).fetchall()]

    user = user_model.get_by_id(uid)
    data = {
        "exporte_le": datetime.now().isoformat(timespec="seconds"),
        "profil": {"nom": user["full_name"], "email": user["email"], "cree_le": user["created_at"]},
        "parametres": settings_model.get(uid),
        "transactions": rows(
            "SELECT t.date, t.type, t.amount AS montant, c.name AS categorie, t.description "
            "FROM transactions t JOIN categories c ON c.id = t.category_id "
            "WHERE t.user_id = ? ORDER BY t.date, t.id"),
        "budgets": rows(
            "SELECT b.month AS mois, c.name AS categorie, b.amount AS montant "
            "FROM budgets b LEFT JOIN categories c ON c.id = b.category_id "
            "WHERE b.user_id = ? ORDER BY b.month"),
        "objectifs_epargne": rows(
            "SELECT id, name AS nom, target_amount AS montant_cible, saved_amount AS montant_economise, "
            "deadline AS date_limite, description FROM savings_goals WHERE user_id = ?"),
        "versements": rows(
            "SELECT sc.goal_id AS objectif_id, sc.amount AS montant, sc.date "
            "FROM savings_contributions sc JOIN savings_goals g ON g.id = sc.goal_id "
            "WHERE g.user_id = ? ORDER BY sc.date"),
        "notifications": rows(
            "SELECT message, type, is_read AS lue, created_at FROM notifications "
            "WHERE user_id = ? ORDER BY id"),
    }
    filename = f"ecobudget-export-{datetime.now().strftime('%Y-%m-%d')}.json"
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@settings_bp.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    uid = session["user_id"]
    user = user_model.get_with_hash(uid)
    password = request.form.get("password", "")

    if not password or not check_password_hash(user["password_hash"], password):
        flash("Mot de passe incorrect : votre compte n'a pas été supprimé.", "error")
        return redirect(url_for("settings.index"))

    user_model.delete_user(uid)
    session.clear()
    flash("Votre compte et toutes vos données ont été supprimés.", "success")
    return redirect(url_for("auth.login"))