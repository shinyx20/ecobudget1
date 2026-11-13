
import math
from datetime import datetime

from flask import Blueprint, flash, jsonify, render_template, request, session

from models import transaction as tx
from routes.auth import login_required
from models import notification as notif
from models import advisor
transactions_bp = Blueprint("transactions", __name__)


def _valid_date(value):
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return 2000 <= d.year <= 2100
    except (TypeError, ValueError):
        return False


def validate(data):
    """Validation côté serveur. Retourne (valeurs_nettoyées, erreurs)."""
    errors = {}

    type_ = data.get("type")
    if type_ not in ("income", "expense"):
        errors["type"] = "Choisissez le type : revenu ou dépense."

    # Montant
    amount = None
    raw = str(data.get("amount", "")).replace(" ", "").replace(",", ".")
    if not raw:
        errors["amount"] = "Veuillez saisir un montant."
    else:
        try:
            amount = round(float(raw), 2)
            if not math.isfinite(amount) or amount <= 0:
                errors["amount"] = "Le montant doit être supérieur à 0."
            elif amount > 1_000_000_000:
                errors["amount"] = "Montant trop élevé."
        except ValueError:
            errors["amount"] = "Montant invalide (exemple : 2500 ou 2500,50)."

    # Catégorie (doit exister ET correspondre au type)
    category_id = None
    try:
        category_id = int(data.get("category_id"))
    except (TypeError, ValueError):
        errors["category_id"] = "Veuillez choisir une catégorie."

    if category_id is not None:
        cat = tx.get_category(category_id)
        if cat is None:
            errors["category_id"] = "Catégorie introuvable."
        elif type_ in ("income", "expense") and cat["type"] != type_:
            errors["category_id"] = "Cette catégorie ne correspond pas au type choisi."

    # Date
    date = str(data.get("date", "")).strip()
    if not date:
        errors["date"] = "Veuillez choisir une date."
    elif not _valid_date(date):
        errors["date"] = "Date invalide."

    # Description (facultative)
    description = " ".join(str(data.get("description", "")).split())
    if len(description) > 200:
        errors["description"] = "La description est limitée à 200 caractères."

    clean = {
        "type": type_,
        "amount": amount,
        "category_id": category_id,
        "date": date,
        "description": description,
    }

    return clean, errors


def flash_budget_alerts(user_id, clean):
    """Après une dépense : alertes de budget + détection de dépense inhabituelle."""
    if clean["type"] != "expense":
        return
    for message, level in notif.check_budget_alerts(user_id, clean["date"][:7]):
        flash(message, "error" if level == "danger" else "warning")
    for message, level in advisor.check_unusual_alerts(user_id):
        flash(message, "warning")

# ---------- Page principale ----------
@transactions_bp.route("/transactions")
@login_required
def index():
    user_id = session["user_id"]

    q = request.args.get("q", "").strip()[:100]
    type_ = request.args.get("type", "")

    if type_ not in ("income", "expense"):
        type_ = ""

    try:
        category_id = int(request.args.get("category", ""))
    except ValueError:
        category_id = None

    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    if date_from and not _valid_date(date_from):
        date_from = ""

    if date_to and not _valid_date(date_to):
        date_to = ""

    if date_from and date_to and date_from > date_to:
        flash("La date de début doit être antérieure à la date de fin.", "warning")
        date_from = date_to = ""

    transactions = tx.list_transactions(
        user_id, q, type_, category_id, date_from, date_to
    )

    total_income = sum(
        t["amount"] for t in transactions if t["type"] == "income"
    )

    total_expense = sum(
        t["amount"] for t in transactions if t["type"] == "expense"
    )

    filters = {
        "q": q,
        "type": type_,
        "category": category_id,
        "date_from": date_from,
        "date_to": date_to,
    }

    has_filters = any([q, type_, category_id, date_from, date_to])

    categories = tx.get_categories()

    return render_template(
        "transactions.html",
        transactions=transactions,
        categories=categories,
        filters=filters,
        has_filters=has_filters,
        total_count=tx.count_all(user_id),
        total_income=total_income,
        total_expense=total_expense,
    )


# ---------- Actions (JSON) ----------
@transactions_bp.route("/transactions/add", methods=["POST"])
@login_required
def add():
    data = request.get_json(silent=True) or {}
    clean, errors = validate(data)

    if errors:
        return jsonify(ok=False, errors=errors), 400

    tx.create(
        session["user_id"],
        clean["category_id"],
        clean["type"],
        clean["amount"],
        clean["description"],
        clean["date"],
    )

    label = "Revenu" if clean["type"] == "income" else "Dépense"
    flash(f"{label} ajouté avec succès.", "success")
    flash_budget_alerts(session["user_id"], clean)

    return jsonify(ok=True)


@transactions_bp.route("/transactions/<int:tx_id>/edit", methods=["POST"])
@login_required
def edit(tx_id):
    data = request.get_json(silent=True) or {}
    clean, errors = validate(data)

    if errors:
        return jsonify(ok=False, errors=errors), 400

    done = tx.update(
        session["user_id"],
        tx_id,
        clean["category_id"],
        clean["type"],
        clean["amount"],
        clean["description"],
        clean["date"],
    )

    if not done:
        return jsonify(ok=False, message="Transaction introuvable."), 404

    flash("Transaction modifiée avec succès.", "success")
    flash_budget_alerts(session["user_id"], clean)

    return jsonify(ok=True)


@transactions_bp.route("/transactions/<int:tx_id>/delete", methods=["POST"])
@login_required
def delete(tx_id):
    if not tx.delete(session["user_id"], tx_id):
        return jsonify(ok=False, message="Transaction introuvable."), 404

    flash("Transaction supprimée.", "success")

    return jsonify(ok=True)
