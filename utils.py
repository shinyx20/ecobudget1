import math
from datetime import datetime
from flask import g

def parse_amount(raw, allow_zero=False):
    """Retourne (valeur, message_d_erreur). Accepte '2500', '2 500' ou '2500,50'."""
    text = str(raw if raw is not None else "")
    text = text.replace(" ", "").replace("\u202f", "").replace("\u00a0", "").replace(",", ".")
    if not text:
        return None, "Veuillez saisir un montant."
    try:
        value = round(float(text), 2)
    except ValueError:
        return None, "Montant invalide (exemple : 2500 ou 2500,50)."
    if not math.isfinite(value):
        return None, "Montant invalide (exemple : 2500 ou 2500,50)."
    if value < 0 or (value == 0 and not allow_zero):
        return None, "Le montant doit être supérieur à 0."
    if value > 1_000_000_000:
        return None, "Montant trop élevé."
    return value, None


def valid_date(value):
    try:
        d = datetime.strptime(str(value), "%Y-%m-%d")
        return 2000 <= d.year <= 2100
    except ValueError:
        return False




# ---------- Devise choisie par l'utilisateur (Paramètres) ----------
CURRENCY_SYMBOLS = {"DA": "DA", "DZD": "DZD", "EUR": "€", "USD": "$"}


def currency_symbol():
    return CURRENCY_SYMBOLS.get(g.get("currency", "DA"), "DA")


def format_money(value, decimals=2):
    """2500.5 -> '2 500,50 DA' (le symbole dépend de la devise choisie)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    text = f"{value:,.{decimals}f}".replace(",", "\u202f").replace(".", ",")
    return f"{text}\u00a0{currency_symbol()}"  