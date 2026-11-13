import re
import secrets

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from models import goal as goal_model
from models import transaction as tx
from models import user as user_model
from routes.auth import EMAIL_RE, login_required

profile_bp = Blueprint("profile", __name__)

MAX_PHOTO = 2 * 1024 * 1024  # 2 Mo


def _render(errors=None, form=None):
    uid = session["user_id"]
    stats = {"transactions": tx.count_all(uid), "goals": goal_model.count(uid)}
    return render_template("profile.html", errors=errors or {}, form=form or {}, stats=stats)


def _detect_mime(head):
    """Vérifie le contenu réel du fichier (pas seulement son nom)."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


@profile_bp.route("/profile")
@login_required
def index():
    return _render()


@profile_bp.route("/avatar")
@login_required
def avatar():
    """Photo de l'utilisateur connecté (lue dans la base)."""
    row = user_model.get_photo(session["user_id"])
    if not row or not row["photo_data"]:
        abort(404)
    response = Response(bytes(row["photo_data"]), mimetype=row["photo_mime"] or "image/png")
    response.headers["Cache-Control"] = "private, max-age=86400"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@profile_bp.route("/profile/update", methods=["POST"])
@login_required
def update():
    uid = session["user_id"]
    full_name = " ".join(request.form.get("full_name", "").split())
    email = request.form.get("email", "").strip().lower()
    errors = {}

    if not full_name:
        errors["full_name"] = "Veuillez saisir votre nom complet."
    elif len(full_name) < 2 or len(full_name) > 60:
        errors["full_name"] = "Le nom doit contenir entre 2 et 60 caractères."

    if not email:
        errors["email"] = "Veuillez saisir votre adresse email."
    elif not EMAIL_RE.match(email) or len(email) > 120:
        errors["email"] = "Adresse email invalide (exemple : nom@mail.com)."
    elif user_model.email_taken(email, uid):
        errors["email"] = "Cette adresse email est déjà utilisée."

    if not errors and not user_model.update_profile(uid, full_name, email):
        errors["email"] = "Cette adresse email est déjà utilisée."

    if errors:
        flash("Les informations n'ont pas été enregistrées. Vérifiez les champs en rouge.", "error")
        return _render(errors, {"full_name": full_name, "email": email})

    flash("Vos informations ont été mises à jour.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/profile/password", methods=["POST"])
@login_required
def password():
    uid = session["user_id"]
    user = user_model.get_with_hash(uid)
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    errors = {}

    if not current:
        errors["current_password"] = "Veuillez saisir votre mot de passe actuel."
    elif not check_password_hash(user["password_hash"], current):
        errors["current_password"] = "Mot de passe actuel incorrect."

    if not new:
        errors["new_password"] = "Veuillez saisir un nouveau mot de passe."
    elif len(new) < 8:
        errors["new_password"] = "Minimum 8 caractères."
    elif not (re.search(r"[A-Za-z]", new) and re.search(r"\d", new)):
        errors["new_password"] = "Le mot de passe doit contenir au moins une lettre et un chiffre."
    elif new == current:
        errors["new_password"] = "Le nouveau mot de passe doit être différent de l'ancien."

    if not confirm:
        errors["confirm_password"] = "Veuillez confirmer le nouveau mot de passe."
    elif confirm != new:
        errors["confirm_password"] = "Les mots de passe ne correspondent pas."

    if errors:
        flash("Le mot de passe n'a pas été modifié. Vérifiez les champs en rouge.", "error")
        return _render(errors)

    user_model.update_password(uid, generate_password_hash(new))
    flash("Votre mot de passe a été modifié.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/profile/photo", methods=["POST"])
@login_required
def photo():
    uid = session["user_id"]
    file = request.files.get("photo")

    if not file or not file.filename:
        flash("Veuillez choisir une image.", "error")
        return _render({"photo": "Veuillez choisir une image."})

    data = file.read(MAX_PHOTO + 1)
    if len(data) > MAX_PHOTO:
        flash("Image trop volumineuse (2 Mo maximum).", "error")
        return _render({"photo": "Image trop volumineuse (2 Mo maximum)."})

    mime = _detect_mime(data[:12])
    if mime is None:
        flash("Format non pris en charge. Utilisez PNG, JPG ou WebP.", "error")
        return _render({"photo": "Format non pris en charge (PNG, JPG ou WebP)."})

    user_model.set_photo(uid, secrets.token_hex(6), data, mime)
    flash("Votre photo de profil a été mise à jour.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/profile/photo/delete", methods=["POST"])
@login_required
def photo_delete():
    user_model.clear_photo(session["user_id"])
    flash("Votre photo de profil a été supprimée.", "success")
    return redirect(url_for("profile.index"))