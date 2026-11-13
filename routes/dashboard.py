from datetime import date

from flask import Blueprint, render_template, session

from models import budget as budget_model
from models import goal as goal_model
from models import transaction as tx
from routes.auth import login_required
from models import advisor
from utils import format_money

dashboard_bp = Blueprint("dashboard", __name__)

MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MONTHS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

def _da(value):
    return format_money(value, 0)

def last_months(n, today):
    """['2026-06', ..., '2026-11'] : les n derniers mois, du plus ancien au plus récent."""
    months = []
    for i in range(n - 1, -1, -1):
        year, month = today.year, today.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append(f"{year}-{month:02d}")
    return months


def build_alerts(expense, global_budget, categories):
    """Alertes à 80 % (avertissement) et au-delà de 100 % (dépassement)."""
    alerts = []

    def check(name, spent, budget, icon):
        if not budget or budget <= 0:
            return
        pct = spent / budget * 100
        if pct > 100:
            alerts.append({
                "level": "danger", "icon": icon,
                "title": f"{name} : budget dépassé",
                "text": f"Vous avez dépassé votre budget de {_da(spent - budget)} ({round(pct)} % utilisé).",
            })
        elif pct >= 80:
            alerts.append({
                "level": "warning", "icon": icon,
                "title": f"{name} : {round(pct)} % du budget utilisé",
                "text": f"Il vous reste {_da(budget - spent)} pour ce mois.",
            })

    check("Budget global", expense, global_budget, "wallet")
    for c in categories:
        check(c["name"], c["spent"], c["budget"], c["icon"])
    alerts.sort(key=lambda a: 0 if a["level"] == "danger" else 1)
    return alerts


def build_tips(income, expense, prev_expense, by_category, goals, tx_count):
    """Aperçu de conseils basés sur les données réelles (règles simples).
    La page « Conseils intelligents » (étape 10) ira plus loin."""
    if tx_count == 0:
        return [{"icon": "lightbulb", "level": "info",
                 "text": "Ajoutez vos premières transactions : des conseils personnalisés apparaîtront ici."}]
    tips = []

    if prev_expense > 0 and expense > 0:
        change = (expense - prev_expense) / prev_expense * 100
        if change >= 20:
            tips.append({"icon": "trending-up", "level": "warning",
                         "text": f"Vos dépenses de ce mois sont en hausse de {round(change)} % par rapport au mois dernier."})
        elif change <= -10:
            tips.append({"icon": "trending-down", "level": "success",
                         "text": f"Bravo ! Vos dépenses ont baissé de {round(abs(change))} % par rapport au mois dernier."})

    if by_category and expense > 0:
        top = by_category[0]
        share = top["total"] / expense * 100
        if share >= 40:
            tips.append({"icon": "chart-pie", "level": "info",
                         "text": f"La catégorie « {top['name']} » représente {round(share)} % de vos dépenses ce mois-ci."})

    if income > 0 and expense > income:
        tips.append({"icon": "triangle-alert", "level": "warning",
                     "text": f"Vos dépenses dépassent vos revenus de {_da(expense - income)} ce mois-ci."})
    elif income > 0 and (income - expense) / income >= 0.2:
        rate = (income - expense) / income * 100
        tips.append({"icon": "piggy-bank", "level": "success",
                     "text": f"Vous avez conservé {round(rate)} % de vos revenus ce mois-ci."})

    for g in goals:
        if 80 <= g["percent"] < 100:
            tips.append({"icon": "target", "level": "success",
                         "text": f"Vous êtes proche d'atteindre votre objectif « {g['name']} » ({g['percent']} %)."})

    if not tips:
        tips.append({"icon": "lightbulb", "level": "info",
                     "text": "Vos finances sont stables ce mois-ci. Continuez ainsi !"})
    return tips[:3]


@dashboard_bp.route("/dashboard")
@login_required
def index():
    uid = session["user_id"]
    today = date.today()
    month = today.strftime("%Y-%m")
    months = last_months(6, today)

    income, expense = tx.month_totals(uid, month)
    balance = tx.total_balance(uid)
    by_category = tx.expenses_by_category(uid, month)
    series = tx.monthly_totals(uid, months[0])
    prev_expense = series.get(months[-2], {}).get("expense", 0)
    tx_count = tx.count_all(uid)

    global_budget = budget_model.get_global(uid, month)
    cat_budgets = budget_model.category_status(uid, month)
    all_goals = goal_model.list_goals(uid)

    budget_remaining = (global_budget - expense) if global_budget else None
    budget_percent = round(expense / global_budget * 100) if global_budget else 0

    charts = {
        "months": [MONTHS_SHORT[int(m[5:]) - 1] for m in months],
        "income": [series.get(m, {}).get("income", 0) for m in months],
        "expense": [series.get(m, {}).get("expense", 0) for m in months],
        "categories": [{"name": c["name"], "amount": c["total"]} for c in by_category],
    }

    return render_template(
        "dashboard.html",
        month_label=f"{MONTHS_LONG[today.month - 1]} {today.year}",
        balance=balance, income=income, expense=expense,
        global_budget=global_budget, budget_remaining=budget_remaining,
        budget_percent=budget_percent,
        alerts=build_alerts(expense, global_budget, cat_budgets),
        tips=advisor.dashboard_tips(uid),
        recent=tx.recent(uid, 5),
        total_count=tx_count,
        charts=charts,
    )