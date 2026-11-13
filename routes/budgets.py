from datetime import date

from flask import Blueprint, flash, jsonify, render_template, request, session

from models import budget as budget_model
from models import notification as notif
from models import transaction as tx
from routes.auth import login_required
from utils import parse_amount

budgets_bp = Blueprint("budgets", __name__)


def flash_alerts(alerts):
    for message, level in alerts:
        flash(message, "error" if level == "danger" else "warning")


@budgets_bp.route("/budgets")
@login_required
def index():
    uid = session["user_id"]
    current = date.today().strftime("%Y-%m")
    month = request.args.get("month", "")
    if not budget_model.valid_month(month):
        month = current

    global_b = budget_model.global_status(uid, month)
    cats = budget_model.category_status(uid, month)
    prev_month = budget_model.shift_month(month, -1)
    can_copy = (not global_b and not cats
                and budget_model.count_for_month(uid, prev_month) > 0)

    return render_template(
        "budgets.html",
        month=month,
        month_label=notif.month_label(month),
        prev_month=prev_month,
        next_month=budget_model.shift_month(month, 1),
        is_current=(month == current),
        g=global_b,
        cats=cats,
        expense_categories=[c for c in tx.get_categories() if c["type"] == "expense"],
        can_copy=can_copy,
        prev_label=notif.month_label(prev_month),
    )


@budgets_bp.route("/budgets/save", methods=["POST"])
@login_required
def save():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    errors = {}

    month = str(data.get("month", ""))
    if not budget_model.valid_month(month):
        errors["month"] = "Mois invalide."

    category_id = None
    raw_cat = data.get("category_id")
    if raw_cat not in (None, ""):
        try:
            category_id = int(raw_cat)
        except (TypeError, ValueError):
            errors["category_id"] = "Catégorie invalide."
        else:
            cat = tx.get_category(category_id)
            if cat is None or cat["type"] != "expense":
                errors["category_id"] = "Choisissez une catégorie de dépenses."

    amount, err = parse_amount(data.get("amount"))
    if err:
        errors["amount"] = err

    if errors:
        return jsonify(ok=False, errors=errors), 400

    budget_model.save(uid, month, category_id, amount)
    flash("Budget enregistré.", "success")
    flash_alerts(notif.check_budget_alerts(uid, month))
    return jsonify(ok=True)


@budgets_bp.route("/budgets/<int:budget_id>/delete", methods=["POST"])
@login_required
def delete(budget_id):
    if not budget_model.delete(session["user_id"], budget_id):
        return jsonify(ok=False, message="Budget introuvable."), 404
    flash("Budget supprimé.", "success")
    return jsonify(ok=True)


@budgets_bp.route("/budgets/copy", methods=["POST"])
@login_required
def copy():
    data = request.get_json(silent=True) or {}
    month = str(data.get("month", ""))
    if not budget_model.valid_month(month):
        return jsonify(ok=False, message="Mois invalide."), 400

    uid = session["user_id"]
    copied = budget_model.copy_from_previous(uid, month)
    if copied == 0:
        return jsonify(ok=False, message="Aucun budget à copier."), 400
    flash(f"{copied} budget(s) copié(s) depuis le mois précédent.", "success")
    flash_alerts(notif.check_budget_alerts(uid, month))
    return jsonify(ok=True)