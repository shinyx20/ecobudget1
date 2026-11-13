from flask import Blueprint, current_app, flash, redirect, render_template, session, url_for

from models import advisor
from routes.auth import login_required

advice_bp = Blueprint("advice", __name__)


@advice_bp.route("/advice")
@login_required
def index():
    try:
        result = advisor.analyze(session["user_id"])
    except Exception:
        # Le détail de l'erreur est affiché dans le terminal où tourne "python app.py"
        current_app.logger.exception("Conseils : analyse impossible")
        flash("Les conseils n'ont pas pu être calculés. Réessayez dans un instant.", "error")
        return redirect(url_for("dashboard.index"))
    return render_template("advice.html", **result)