import math
from datetime import date, datetime

from flask import Blueprint, flash, jsonify, render_template, request, session

from models import goal as goal_model
from models import notification as notif
from routes.auth import login_required
from utils import parse_amount, valid_date
from utils import format_money, parse_amount, valid_date



goals_bp = Blueprint("goals", __name__)


def _enrich(g, today):
    """Ajoute : reste à économiser, jours restants, épargne mensuelle conseillée."""
    g["remaining"] = max(0, g["target_amount"] - g["saved_amount"])
    g["done"] = g["saved_amount"] >= g["target_amount"]
    g["days_left"] = None
    g["overdue"] = False
    g["monthly"] = None
    try:
        deadline = datetime.strptime(g["deadline"], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return g
    delta = (deadline - today).days
    g["days_left"] = delta
    if not g["done"]:
        if delta < 0:
            g["overdue"] = True
        else:
            months = max(1, math.ceil(delta / 30))
            g["monthly"] = g["remaining"] / months
    return g


def _progress_notification(uid, goal):
    """Notification quand l'objectif est proche (80 %) ou atteint."""
    saved, target = goal["saved_amount"], goal["target_amount"]
    if target <= 0:
        return
    if saved >= target:
        message, level = f"Félicitations ! Objectif « {goal['name']} » atteint.", "success"
    elif saved >= 0.8 * target:
        message, level = f"Vous êtes proche d'atteindre votre objectif « {goal['name']} » (80 % atteint).", "info"
    else:
        return
    if notif.create(uid, message, level):
        flash(message, "success" if level == "success" else "info")


def _validate(data, existing=None):
    errors = {}

    name = " ".join(str(data.get("name", "")).split())
    if not name:
        errors["name"] = "Veuillez saisir le nom de l'objectif."
    elif len(name) < 2 or len(name) > 80:
        errors["name"] = "Le nom doit contenir entre 2 et 80 caractères."

    target, err = parse_amount(data.get("target_amount"))
    if err:
        errors["target_amount"] = err

    saved = 0.0
    if existing is None:  # le montant de départ n'existe qu'à la création
        raw = str(data.get("saved_amount", "")).strip()
        if raw:
            saved, err = parse_amount(raw, allow_zero=True)
            if err:
                errors["saved_amount"] = err
            elif target and saved > target:
                errors["saved_amount"] = "Le montant déjà économisé ne peut pas dépasser le montant cible."

    deadline = str(data.get("deadline", "")).strip()
    if not deadline:
        errors["deadline"] = "Veuillez choisir une date limite."
    elif not valid_date(deadline):
        errors["deadline"] = "Date invalide."
    elif (existing is None or deadline != existing["deadline"]) and deadline < date.today().isoformat():
        errors["deadline"] = "La date limite ne peut pas être dans le passé."

    description = " ".join(str(data.get("description", "")).split())
    if len(description) > 300:
        errors["description"] = "La description est limitée à 300 caractères."

    clean = {"name": name, "target": target, "saved": saved,
             "deadline": deadline, "description": description}
    return clean, errors


@goals_bp.route("/goals")
@login_required
def index():
    today = date.today()
    goals = [_enrich(g, today) for g in goal_model.list_goals(session["user_id"])]
    return render_template(
        "goals.html",
        goals=goals,
        total_saved=sum(g["saved_amount"] for g in goals),
        total_target=sum(g["target_amount"] for g in goals),
        done_count=sum(1 for g in goals if g["done"]),
        today=today.isoformat(),
    )


@goals_bp.route("/goals/save", methods=["POST"])
@login_required
def save():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}

    existing = None
    raw_id = data.get("id")
    if raw_id not in (None, ""):
        try:
            existing = goal_model.get_goal(uid, int(raw_id))
        except (TypeError, ValueError):
            existing = None
        if existing is None:
            return jsonify(ok=False, message="Objectif introuvable."), 404

    clean, errors = _validate(data, existing)
    if errors:
        return jsonify(ok=False, errors=errors), 400

    if existing:
        goal_model.update(uid, existing["id"], clean["name"], clean["target"],
                          clean["deadline"], clean["description"])
        flash("Objectif modifié avec succès.", "success")
        goal_id = existing["id"]
    else:
        goal_id = goal_model.create(uid, clean["name"], clean["target"], clean["saved"],
                                    clean["deadline"], clean["description"],
                                    date.today().isoformat())
        flash("Objectif créé avec succès.", "success")

    _progress_notification(uid, goal_model.get_goal(uid, goal_id))
    return jsonify(ok=True)


@goals_bp.route("/goals/<int:goal_id>/contribute", methods=["POST"])
@login_required
def contribute(goal_id):
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    amount, err = parse_amount(data.get("amount"))
    if err:
        return jsonify(ok=False, errors={"amount": err}), 400

    if not goal_model.contribute(uid, goal_id, amount, date.today().isoformat()):
        return jsonify(ok=False, message="Objectif introuvable."), 404

    goal = goal_model.get_goal(uid, goal_id)
    flash(f"{format_money(amount)} ajoutés à « {goal['name']} ».", "success")
    _progress_notification(uid, goal)
    return jsonify(ok=True)


@goals_bp.route("/goals/<int:goal_id>/delete", methods=["POST"])
@login_required
def delete(goal_id):
    if not goal_model.delete(session["user_id"], goal_id):
        return jsonify(ok=False, message="Objectif introuvable."), 404
    flash("Objectif supprimé.", "success")
    return jsonify(ok=True)