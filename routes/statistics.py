from datetime import date, datetime, timedelta

from flask import Blueprint, flash, render_template, request, session

from models import goal as goal_model
from models import transaction as tx
from routes.auth import login_required
from utils import valid_date

statistics_bp = Blueprint("statistics", __name__)

MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _parse(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _bucket_keys(start, end, monthly):
    keys = []
    if monthly:
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            keys.append(f"{y}-{m:02d}")
            m += 1
            if m > 12:
                m, y = 1, y + 1
    else:
        d = start
        while d <= end:
            keys.append(d.isoformat())
            d += timedelta(days=1)
    return keys


def _label(key):
    if len(key) == 10:
        return f"{key[8:10]}/{key[5:7]}"
    return f"{MONTHS_SHORT[int(key[5:7]) - 1]} {key[:4]}"


@statistics_bp.route("/statistics")
@login_required
def index():
    uid = session["user_id"]
    today = date.today()

    period = request.args.get("period", "month")
    if period not in ("week", "month", "year", "custom"):
        period = "month"
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    if period == "week":
        start, end = today - timedelta(days=today.weekday()), today
    elif period == "year":
        start, end = date(today.year, 1, 1), today
    else:
        start, end = today.replace(day=1), today
        if period == "custom" and date_from and date_to:
            if (valid_date(date_from) and valid_date(date_to) and date_from <= date_to
                    and (_parse(date_to) - _parse(date_from)).days <= 1830):
                start, end = _parse(date_from), _parse(date_to)
            else:
                flash("Période invalide : vérifiez les dates (5 ans maximum).", "warning")

    s, e = start.isoformat(), end.isoformat()
    monthly = (end - start).days + 1 > 62
    length = 7 if monthly else 10
    keys = _bucket_keys(start, end, monthly)

    # Revenus / dépenses par période
    totals = tx.range_bucket_totals(uid, s, e, length)
    income = [round(totals.get(k, {}).get("income", 0), 2) for k in keys]
    expense = [round(totals.get(k, {}).get("expense", 0), 2) for k in keys]
    total_income, total_expense = sum(income), sum(expense)

    # Répartition par catégorie
    categories = tx.range_expenses_by_category(uid, s, e)
    for c in categories:
        c["percent"] = round(c["total"] / total_expense * 100) if total_expense else 0

    # Évolution de l'épargne (cumul)
    added_by = goal_model.contributions_by_bucket(uid, s, e, length)
    running = goal_model.contributions_before(uid, s)
    savings = []
    for k in keys:
        running += added_by.get(k, 0)
        savings.append(round(running, 2))
    savings_added = sum(added_by.values())

    charts = {
        "labels": [_label(k) for k in keys],
        "income": income,
        "expense": expense,
        "categories": [{"name": c["name"], "amount": c["total"]} for c in categories],
        "savings": savings,
    }

    return render_template(
        "statistics.html",
        period=period,
        start=s, end=e,
        range_label=f"Du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}",
        total_income=total_income,
        total_expense=total_expense,
        savings_added=savings_added,
        savings_total=running,
        top_categories=categories[:5],
        has_data=(total_income + total_expense) > 0,
        charts=charts,
    )