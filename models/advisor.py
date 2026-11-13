import calendar
import math
from datetime import date, datetime, timedelta

from flask import current_app

from database import get_db
from models import budget as budget_model
from models import goal as goal_model
from models import notification as notif
from models import transaction as tx

# ---------- Seuils des règles (modifiables) ----------
UNUSUAL_RATIO = 1.5        # semaine >= 150 % de la moyenne
UNUSUAL_MIN_DIFF = 1000    # et au moins 1 000 DA d'écart
HISTORY_WEEKS = 4          # nombre de semaines de référence
MIN_HISTORY_WEEKS = 2      # semaines minimum avec dépenses pour avoir une "habitude"
MONTH_INCREASE = 30        # hausse mensuelle (%) à signaler
MONTH_MIN_DIFF = 1000
DISCRETIONARY = ("Loisirs", "Shopping", "Autres")
LEVEL_ORDER = {"danger": 0, "warning": 1, "info": 2, "success": 3}


# ---------- Utilitaires ----------
def _da(value):
    """Montant formaté avec la devise choisie (avec solution de secours)."""
    try:
        from utils import format_money
        return format_money(value, 0)
    except Exception:
        return f"{float(value):,.0f}".replace(",", "\u202f") + "\u00a0DA"


def _day(text):
    return datetime.strptime(str(text), "%Y-%m-%d").date()


def _fetch(user_id, start_iso):
    """Dépenses de l'utilisateur depuis une date (toujours filtrées par user_id)."""
    return get_db().execute(
        "SELECT t.date, t.amount, c.id AS cid, c.name, c.icon "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.user_id = ? AND t.type = 'expense' AND t.date >= ?",
        (user_id, start_iso),
    ).fetchall()


def _insight(kind, level, icon, title, text, why, link=None):
    return {"kind": kind, "level": level, "icon": icon, "title": title,
            "text": text, "why": why, "link": link}


def _safe(label, problems, func, *args):
    """Exécute une règle. Si elle échoue : on journalise l'erreur dans le terminal
    et on continue avec les autres règles (la page ne plante pas)."""
    try:
        return func(*args)
    except Exception:
        current_app.logger.exception("Conseils : erreur dans la règle « %s »", label)
        problems.append(label)
        return []


def _empty_weekly(today):
    monday = today - timedelta(days=today.weekday())
    return {"rows": [], "monday": monday, "has_history": False,
            "week_label": f"Semaine du {monday.strftime('%d/%m')} au {today.strftime('%d/%m')}"}


# ---------- 1. Dépenses inhabituelles (semaine en cours vs habitude) ----------
def weekly_analysis(user_id, today=None):
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    start = monday - timedelta(days=7 * HISTORY_WEEKS)

    cats = {}
    for r in _fetch(user_id, start.isoformat()):
        d = _day(r["date"])
        if d > today:
            continue
        idx = (monday - (d - timedelta(days=d.weekday()))).days // 7  # 0 = semaine en cours
        if 0 <= idx <= HISTORY_WEEKS:
            c = cats.setdefault(r["name"], {"icon": r["icon"], "cid": r["cid"],
                                            "weeks": [0.0] * (HISTORY_WEEKS + 1)})
            c["weeks"][idx] += r["amount"]

    rows, has_history = [], False
    for name, c in cats.items():
        current = c["weeks"][0]
        past = [w for w in c["weeks"][1:] if w > 0]
        average = sum(past) / len(past) if past else 0.0
        enough = len(past) >= MIN_HISTORY_WEEKS
        has_history = has_history or enough
        if current == 0:
            continue

        if not enough:
            status = "new"
        elif current >= UNUSUAL_RATIO * average and current - average >= UNUSUAL_MIN_DIFF:
            status = "unusual"
        elif current > 1.2 * average:
            status = "high"
        else:
            status = "normal"

        rows.append({
            "name": name, "icon": c["icon"], "cid": c["cid"],
            "current": current, "average": average, "weeks_used": len(past),
            "change": round((current - average) / average * 100) if average else None,
            "status": status,
        })

    order = {"unusual": 0, "high": 1, "normal": 2, "new": 3}
    rows.sort(key=lambda w: (order[w["status"]], -w["current"]))
    return {
        "rows": rows,
        "monday": monday,
        "has_history": has_history,
        "week_label": f"Semaine du {monday.strftime('%d/%m')} au {today.strftime('%d/%m')}",
    }


def _unusual_insights(weekly):
    out = []
    for w in weekly["rows"]:
        if w["status"] != "unusual":
            continue
        level = "danger" if w["current"] >= 2.5 * w["average"] else "warning"
        out.append(_insight(
            "unusual", level, "triangle-alert",
            f"Dépenses inhabituelles : {w['name']}",
            f"Vous avez dépensé {_da(w['current'])} en {w['name']} cette semaine, "
            f"contre {_da(w['average'])} en moyenne par semaine (+{w['change']} %).",
            f"Règle : on compare votre semaine en cours (depuis lundi) à la moyenne de vos "
            f"{w['weeks_used']} dernières semaines de dépenses dans cette catégorie. "
            f"Alerte si le montant dépasse la moyenne de 50 % ou plus et d'au moins {_da(UNUSUAL_MIN_DIFF)}.",
            {"url": f"/transactions?category={w['cid']}", "label": "Voir les transactions"},
        ))
    return out


def check_unusual_alerts(user_id, today=None):
    """Crée une notification par catégorie et par semaine. Ne fait jamais planter l'appelant."""
    try:
        weekly = weekly_analysis(user_id, today)
        created = []
        for w in weekly["rows"]:
            if w["status"] == "unusual":
                message = (f"Dépenses inhabituelles en {w['name']} cette semaine "
                           f"(semaine du {weekly['monday'].strftime('%d/%m')}).")
                if notif.create(user_id, message, "warning"):
                    created.append((message, "warning"))
        return created
    except Exception:
        current_app.logger.exception("Conseils : détection des dépenses inhabituelles impossible")
        return []


# ---------- 2. Tendances du mois (même période vs mois précédent) ----------
def _month_data(user_id, today):
    first_this = today.replace(day=1)
    prev_last = first_this - timedelta(days=1)
    prev_first = prev_last.replace(day=1)
    cap = min(today.day, prev_last.day)   # même nombre de jours écoulés

    cur, prev = {}, {}
    for r in _fetch(user_id, prev_first.isoformat()):
        d = _day(r["date"])
        if d > today:
            continue
        if d >= first_this:
            bucket = cur
        elif d.day <= cap:
            bucket = prev
        else:
            continue
        e = bucket.setdefault(r["name"], {"amount": 0.0, "icon": r["icon"], "cid": r["cid"]})
        e["amount"] += r["amount"]
    return cur, prev


def _trend_insights(cur, prev, today):
    out = []
    cur_total = sum(e["amount"] for e in cur.values())
    prev_total = sum(e["amount"] for e in prev.values())
    elapsed = today.day

    if elapsed >= 5:
        ups = []
        for name, e in cur.items():
            p = prev.get(name, {}).get("amount", 0)
            if p > 0:
                diff = e["amount"] - p
                pct = round(diff / p * 100)
                if pct >= MONTH_INCREASE and diff >= MONTH_MIN_DIFF:
                    ups.append((diff, name, e, p, pct))
        ups.sort(key=lambda x: x[0], reverse=True)
        for diff, name, e, p, pct in ups[:3]:
            out.append(_insight(
                "trend", "warning", "trending-up", f"{name} : dépenses en hausse",
                f"Vos dépenses de {name} ont augmenté de {pct} % par rapport à la même période "
                f"du mois dernier ({_da(e['amount'])} contre {_da(p)}).",
                f"Règle : on compare vos dépenses du 1er au {elapsed} de ce mois avec la même période "
                f"du mois précédent. Alerte si la hausse atteint {MONTH_INCREASE} % et {_da(MONTH_MIN_DIFF)} minimum.",
                {"url": f"/transactions?category={e['cid']}", "label": "Voir les transactions"},
            ))

        if prev_total > 0:
            diff = cur_total - prev_total
            if cur_total <= prev_total * 0.8 and -diff >= MONTH_MIN_DIFF:
                out.append(_insight(
                    "trend", "success", "trending-down", "Vos dépenses diminuent",
                    f"Bravo ! Vos dépenses sont en baisse de {round(-diff / prev_total * 100)} % "
                    f"par rapport à la même période du mois dernier.",
                    f"Règle : dépenses du 1er au {elapsed} de ce mois ({_da(cur_total)}) comparées à la même "
                    f"période du mois précédent ({_da(prev_total)}). Félicitations si la baisse dépasse 20 %.",
                ))
            elif cur_total >= prev_total * 1.2 and diff >= 2 * MONTH_MIN_DIFF:
                out.append(_insight(
                    "trend", "warning", "trending-up", "Dépenses totales en hausse",
                    f"Vos dépenses totales sont en hausse de {round(diff / prev_total * 100)} % "
                    f"par rapport à la même période du mois dernier.",
                    f"Règle : dépenses du 1er au {elapsed} de ce mois ({_da(cur_total)}) comparées à la même "
                    f"période du mois précédent ({_da(prev_total)}). Alerte si la hausse dépasse 20 %.",
                ))

    if cur and cur_total >= 2000:
        name, e = max(cur.items(), key=lambda kv: kv[1]["amount"])
        share = round(e["amount"] / cur_total * 100)
        if share >= 40:
            out.append(_insight(
                "trend", "info", "chart-pie", f"{name} : votre premier poste de dépenses",
                f"La catégorie {name} représente {share} % de vos dépenses ce mois-ci ({_da(e['amount'])}).",
                "Règle : information affichée quand une seule catégorie représente 40 % ou plus des dépenses du mois.",
                {"url": f"/transactions?category={e['cid']}", "label": "Voir les transactions"},
            ))

    disc = {n: e for n, e in cur.items() if n in DISCRETIONARY}
    disc_sum = sum(e["amount"] for e in disc.values())
    if cur_total > 0 and disc_sum >= 2000 and disc_sum / cur_total >= 0.25:
        names = ", ".join(sorted(disc))
        out.append(_insight(
            "saving", "info", "piggy-bank", "Vous pouvez économiser davantage",
            f"{names} représentent {round(disc_sum / cur_total * 100)} % de vos dépenses "
            f"ce mois-ci ({_da(disc_sum)}). En les réduisant de 20 %, vous économiseriez environ "
            f"{_da(disc_sum * 0.2)} sur la base de ce mois.",
            "Règle : les catégories non essentielles (Loisirs, Shopping, Autres) pèsent au moins 25 % de vos "
            "dépenses du mois (2 000 DA minimum). Le calcul applique une réduction de 20 % sur ces catégories.",
            {"url": "/budgets", "label": "Définir un budget"},
        ))
    return out


# ---------- 3. Équilibre revenus / dépenses ----------
def _balance_insights(user_id, income, expense):
    out = []
    if income > 0 and expense > income:
        out.append(_insight(
            "balance", "warning", "triangle-alert", "Dépenses supérieures aux revenus",
            f"Vos dépenses dépassent vos revenus de {_da(expense - income)} ce mois-ci.",
            f"Règle : dépenses du mois ({_da(expense)}) supérieures aux revenus du mois ({_da(income)}).",
            {"url": "/statistics", "label": "Voir les statistiques"},
        ))
    elif income > 0 and (income - expense) / income >= 0.2:
        rate = round((income - expense) / income * 100)
        out.append(_insight(
            "balance", "success", "circle-check", "Bon taux d'épargne",
            f"Vous conservez {rate} % de vos revenus ce mois-ci. Pensez à en placer une partie sur un objectif d'épargne.",
            f"Règle : (revenus {_da(income)} − dépenses {_da(expense)}) ÷ revenus ≥ 20 %.",
            {"url": "/goals", "label": "Voir mes objectifs"},
        ))
    elif income == 0 and expense > 0:
        out.append(_insight(
            "balance", "info", "info", "Aucun revenu enregistré ce mois-ci",
            "Ajoutez vos revenus (bourse, salaire, freelance…) pour obtenir des analyses plus précises.",
            "Règle : des dépenses existent ce mois-ci mais aucun revenu n'a été enregistré.",
            {"url": "/transactions", "label": "Ajouter un revenu"},
        ))
    return out


# ---------- 4. Budgets et prévision de fin de mois ----------
def _budget_insights(user_id, month):
    out = []
    items = []
    g = budget_model.global_status(user_id, month)
    if g:
        items.append(("Budget global", g))
    for c in budget_model.category_status(user_id, month):
        items.append((f"Budget « {c['name']} »", c))

    for name, b in items:
        if b["state"] == "danger":
            out.append(_insight(
                "budget", "danger", "wallet", f"{name} dépassé",
                f"Vous avez dépassé ce budget de {_da(b['spent'] - b['budget'])} ({b['percent']} % utilisé).",
                "Règle : les dépenses du mois sont supérieures au budget défini.",
                {"url": "/budgets", "label": "Gérer mes budgets"},
            ))
        elif b["state"] == "warning":
            out.append(_insight(
                "budget", "warning", "bell-ring", f"{name} : {b['percent']} % utilisé",
                f"Il vous reste {_da(b['remaining'])} pour ce mois.",
                "Règle : alerte dès que 80 % du budget est consommé.",
                {"url": "/budgets", "label": "Gérer mes budgets"},
            ))
    return out


def _forecast_insights(user_id, today, income, expense):
    out = []
    elapsed = today.day
    if elapsed < 7 or expense <= 0:
        return out
    dim = calendar.monthrange(today.year, today.month)[1]
    month = today.strftime("%Y-%m")
    projected = expense / elapsed * dim
    how = (f"Calcul : dépenses du mois ({_da(expense)}) ÷ {elapsed} jours écoulés × {dim} jours "
           f"dans le mois = {_da(projected)}.")

    g = budget_model.global_status(user_id, month)
    if g and g["state"] != "danger" and projected > g["budget"]:
        out.append(_insight(
            "forecast", "warning", "gauge", "Budget global : risque de dépassement",
            f"À ce rythme, vous dépenserez environ {_da(projected)} ce mois-ci, soit "
            f"{_da(projected - g['budget'])} de plus que votre budget global ({_da(g['budget'])}).",
            how, {"url": "/budgets", "label": "Gérer mes budgets"},
        ))
    elif not g and income > 0 and projected > income:
        out.append(_insight(
            "forecast", "warning", "gauge", "Dépenses prévues supérieures à vos revenus",
            f"À ce rythme, vous dépenserez environ {_da(projected)} ce mois-ci, "
            f"alors que vos revenus du mois sont de {_da(income)}.",
            how, {"url": "/budgets", "label": "Définir un budget"},
        ))

    count = 0
    for c in budget_model.category_status(user_id, month):
        if count >= 3:
            break
        if c["state"] != "danger" and c["spent"] > 0:
            proj_c = c["spent"] / elapsed * dim
            if proj_c > c["budget"]:
                out.append(_insight(
                    "forecast", "warning", "gauge", f"{c['name']} : risque de dépassement",
                    f"À ce rythme, vos dépenses de {c['name']} atteindront environ {_da(proj_c)} "
                    f"pour un budget de {_da(c['budget'])}.",
                    f"Calcul : {_da(c['spent'])} dépensés ÷ {elapsed} jours écoulés × {dim} jours = {_da(proj_c)}.",
                    {"url": "/budgets", "label": "Gérer mes budgets"},
                ))
                count += 1
    return out


# ---------- 5. Objectifs d'épargne ----------
def _goal_insights(user_id, today, income, expense):
    out = []
    surplus = max(income - expense, 0)
    for g in goal_model.list_goals(user_id):
        saved, target = g["saved_amount"], g["target_amount"]
        if saved >= target:
            continue
        remaining = target - saved
        name = g["name"]
        link = {"url": "/goals", "label": "Voir mes objectifs"}
        try:
            days = (_day(g["deadline"]) - today).days
        except (TypeError, ValueError):
            days = None

        if g["percent"] >= 80:
            out.append(_insight(
                "goal", "success", "target", f"« {name} » est proche",
                f"Vous êtes proche d'atteindre votre objectif « {name} » : {g['percent']} % atteint, "
                f"il reste {_da(remaining)}.",
                "Règle : information affichée quand un objectif atteint 80 % du montant cible.", link,
            ))
        if days is None:
            continue
        if days < 0:
            out.append(_insight(
                "goal", "warning", "calendar", f"« {name} » : échéance dépassée",
                f"La date limite est passée et il reste {_da(remaining)} à économiser.",
                "Règle : la date limite de l'objectif est dépassée et le montant cible n'est pas atteint.", link,
            ))
        elif days <= 30 and g["percent"] < 80:
            plural = "s" if days > 1 else ""
            out.append(_insight(
                "goal", "warning", "calendar", f"« {name} » : échéance proche",
                f"Il reste {days} jour{plural} pour « {name} » et {_da(remaining)} "
                f"à économiser ({g['percent']} % atteint).",
                "Règle : échéance dans moins de 30 jours avec moins de 80 % du montant atteint.", link,
            ))
        elif days > 0:
            months = max(1, math.ceil(days / 30))
            needed = remaining / months
            if income > 0 and needed > surplus:
                out.append(_insight(
                    "goal", "info", "target", f"« {name} » demande un effort",
                    f"Pour atteindre « {name} » à temps, il faut mettre de côté environ {_da(needed)} par mois, "
                    f"alors que votre solde mensuel actuel est de {_da(surplus)}.",
                    f"Calcul : {_da(remaining)} restants ÷ {months} mois restants = "
                    f"{_da(needed)} par mois, comparés à (revenus − dépenses) du mois en cours.", link,
                ))
    return out


# ---------- Analyse complète ----------
def analyze(user_id, today=None):
    today = today or date.today()
    month = today.strftime("%Y-%m")
    problems = []

    total_count = tx.count_all(user_id)
    base = {"total_count": total_count, "month_label": notif.month_label(month), "problems": problems}

    try:
        weekly = weekly_analysis(user_id, today)
    except Exception:
        current_app.logger.exception("Conseils : analyse hebdomadaire impossible")
        problems.append("dépenses inhabituelles")
        weekly = _empty_weekly(today)
    base["weekly"] = weekly

    if total_count == 0:
        return {**base, "insights": [], "counts": {"attention": 0, "success": 0, "info": 0}}

    try:
        income, expense = tx.month_totals(user_id, month)
    except Exception:
        current_app.logger.exception("Conseils : totaux du mois impossibles")
        problems.append("totaux du mois")
        income = expense = 0.0

    cur, prev = {}, {}
    try:
        cur, prev = _month_data(user_id, today)
    except Exception:
        current_app.logger.exception("Conseils : données du mois impossibles")
        problems.append("tendances")

    insights = []
    insights += _safe("dépenses inhabituelles", problems, _unusual_insights, weekly)
    insights += _safe("budgets", problems, _budget_insights, user_id, month)
    insights += _safe("prévisions", problems, _forecast_insights, user_id, today, income, expense)
    insights += _safe("tendances", problems, _trend_insights, cur, prev, today)
    insights += _safe("équilibre", problems, _balance_insights, user_id, income, expense)
    insights += _safe("objectifs", problems, _goal_insights, user_id, today, income, expense)

    weekly_ok = "dépenses inhabituelles" not in problems
    if weekly_ok and not weekly["has_history"]:
        insights.append(_insight(
            "info", "info", "lightbulb", "Historique encore insuffisant",
            "La détection des dépenses inhabituelles s'active après au moins 2 semaines de dépenses "
            "dans une même catégorie. Continuez à enregistrer vos transactions.",
            f"Règle : il faut au moins {MIN_HISTORY_WEEKS} semaines avec dépenses sur les {HISTORY_WEEKS} "
            f"dernières semaines pour définir une habitude.",
            {"url": "/transactions", "label": "Ajouter une transaction"},
        ))
    elif weekly_ok and not any(i["kind"] == "unusual" for i in insights):
        insights.append(_insight(
            "unusual", "success", "circle-check", "Aucune dépense inhabituelle",
            "Vos dépenses de cette semaine sont conformes à vos habitudes. Continuez ainsi !",
            "Règle : aucune catégorie ne dépasse de 50 % sa moyenne hebdomadaire habituelle.",
        ))

    insights.sort(key=lambda i: LEVEL_ORDER[i["level"]])
    counts = {
        "attention": sum(1 for i in insights if i["level"] in ("danger", "warning")),
        "success": sum(1 for i in insights if i["level"] == "success"),
        "info": sum(1 for i in insights if i["level"] == "info"),
    }
    return {**base, "insights": insights, "counts": counts}


def dashboard_tips(user_id, limit=3):
    """Aperçu pour le dashboard. Ne fait jamais planter le dashboard."""
    empty = [{"icon": "lightbulb", "level": "info",
              "text": "Ajoutez vos premières transactions : des conseils personnalisés apparaîtront ici."}]
    try:
        result = analyze(user_id)
    except Exception:
        current_app.logger.exception("Conseils : aperçu du dashboard impossible")
        return empty
    if result["total_count"] == 0 or not result["insights"]:
        return empty
    return [
        {"icon": i["icon"],
         "level": "warning" if i["level"] in ("danger", "warning") else i["level"],
         "text": i["text"]}
        for i in result["insights"][:limit]
    ]