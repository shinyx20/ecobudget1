from flask import Blueprint, flash, redirect, render_template, session, url_for

from models import notification as notif
from routes.auth import login_required

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications")
@login_required
def index():
    return render_template("notifications.html", items=notif.list_all(session["user_id"]))


@notifications_bp.route("/notifications/read", methods=["POST"])
@login_required
def read_all():
    notif.mark_all_read(session["user_id"])
    flash("Toutes les notifications sont marquées comme lues.", "success")
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/notifications/clear", methods=["POST"])
@login_required
def clear():
    notif.delete_all(session["user_id"])
    flash("Notifications supprimées.", "success")
    return redirect(url_for("notifications.index"))