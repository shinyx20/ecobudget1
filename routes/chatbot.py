import unicodedata
from datetime import date

from flask import Blueprint, jsonify, request, session
from rapidfuzz import fuzz

from models import budget as budget_model
from models import transaction as tx
from routes.auth import login_required
from utils import format_money

chatbot_bp = Blueprint("chatbot", __name__)

# ---------------------------------------------------
# Réponses prédéfinies
# ---------------------------------------------------

REPLIES = {
    "add": {
        "text": (
            "➕ Ajouter une transaction\n\n"
            "1. Ouvrez la page Transactions.\n"
            "2. Cliquez sur « Ajouter une transaction ».\n"
            "3. Choisissez Dépense ou Revenu.\n"
            "4. Saisissez le montant, la catégorie et la date.\n"
            "5. Cliquez sur Enregistrer."
        ),
        "link": {
            "url": "/transactions",
            "label": "Aller aux transactions"
        }
    },

    "budget": {
        "text": (
            "💰 Créer un budget\n\n"
            "1. Ouvrez la page Budgets.\n"
            "2. Cliquez sur « Définir un budget ».\n"
            "3. Saisissez le montant maximum.\n"
            "4. Vous recevrez des alertes à 80 % et 100 %."
        ),
        "link": {
            "url": "/budgets",
            "label": "Aller aux budgets"
        }
    },

    "stats": {
        "text": (
            "📊 La page Statistiques affiche :\n\n"
            "• Les dépenses par catégorie\n"
            "• L'évolution des dépenses\n"
            "• Les revenus vs dépenses\n"
            "• Les graphiques mensuels et annuels"
        ),
        "link": {
            "url": "/statistics",
            "label": "Voir les statistiques"
        }
    },

    "save": {
        "text": (
            "🌱 Conseils pour économiser :\n\n"
            "• Fixez un budget mensuel\n"
            "• Réduisez les dépenses non essentielles\n"
            "• Définissez un objectif d'épargne\n"
            "• Consultez les Conseils intelligents"
        ),
        "link": {
            "url": "/advice",
            "label": "Voir les conseils"
        }
    }
}

# ---------------------------------------------------
# Messages
# ---------------------------------------------------

GREETING = (
    "👋 Bonjour ! Je suis EcoBot.\n\n"
    "Je peux vous aider avec :\n"
    "• Les transactions\n"
    "• Les budgets\n"
    "• Les statistiques\n"
    "• Les économies\n"
    "• Votre situation financière"
)

FALLBACK = (
    "🤔 Je n'ai pas compris votre question.\n\n"
    "Essayez par exemple :\n"
    "• Comment ajouter une transaction ?\n"
    "• How do I create a budget ?\n"
    "• Show my statistics\n"
    "• Comment économiser de l'argent ?\n"
    "• Quelle est ma situation financière ?"
)

# ---------------------------------------------------
# Phrases FR + EN
# ---------------------------------------------------

INTENTS = {
    "add": [
        "ajouter une transaction",
        "nouvelle transaction",
        "ajouter depense",
        "ajouter revenu",
        "saisir transaction",
        "create transaction",
        "add transaction",
        "new expense",
        "new income",
        "record expense",
        "record income"
    ],

    "budget": [
        "budget",
        "creer budget",
        "definir budget",
        "plafond",
        "limite budget",
        "create budget",
        "set budget",
        "budget limit",
        "spending limit"
    ],

    "stats": [
        "statistiques",
        "graphiques",
        "analyse",
        "rapport",
        "statistics",
        "stats",
        "chart",
        "report",
        "analysis"
    ],

    "save": [
        "economiser",
        "epargne",
        "reduire depenses",
        "conseils",
        "save money",
        "saving",
        "reduce expenses",
        "tips",
        "financial advice"
    ],

    "situation": [
        "situation",
        "solde",
        "combien depense",
        "ce mois",
        "mon budget",
        "balance",
        "financial situation",
        "how much spent",
        "how am i doing",
        "monthly status",
        "my finances"
    ]
}

GREETINGS = [
    "bonjour",
    "salut",
    "bonsoir",
    "hello",
    "hi",
    "hey",
    "good morning",
    "good evening"
]

# ---------------------------------------------------
# Utilitaires
# ---------------------------------------------------

def _normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )

# ---------------------------------------------------
# Détection intelligente
# ---------------------------------------------------

def detect_topic(message):

    text = _normalize(message)

    # Salutations
    if any(g in text for g in GREETINGS):
        return "greeting"

    best_topic = None
    best_score = 0

    for topic, examples in INTENTS.items():

        for sentence in examples:

            score = fuzz.partial_ratio(
                text,
                _normalize(sentence)
            )

            if score > best_score:
                best_score = score
                best_topic = topic

    # seuil minimal
    if best_score >= 65:
        return best_topic

    return None

# ---------------------------------------------------
# Situation utilisateur
# ---------------------------------------------------

def situation_reply(user_id):

    month = date.today().strftime("%Y-%m")

    income, expense = tx.month_totals(user_id, month)

    if income == 0 and expense == 0:

        return {
            "text": (
                "📭 Aucune transaction enregistrée ce mois-ci.\n\n"
                "Ajoutez des revenus et dépenses pour recevoir une analyse."
            ),
            "link": {
                "url": "/transactions",
                "label": "Ajouter une transaction"
            }
        }

    balance = income - expense

    lines = [
        f"💰 Revenus : {format_money(income)}",
        f"💸 Dépenses : {format_money(expense)}",
        f"📊 Solde : {format_money(balance)}"
    ]

    top = tx.expenses_by_category(user_id, month)

    if top:
        lines.append(
            f"🏷️ Plus grosse dépense : "
            f"{top[0]['name']} "
            f"({format_money(top[0]['total'])})"
        )

    budget = budget_model.global_status(user_id, month)

    if budget:

        if budget["remaining"] >= 0:

            lines.append(
                f"✅ Budget utilisé : "
                f"{budget['percent']} %"
            )

            lines.append(
                f"💵 Restant : "
                f"{format_money(budget['remaining'])}"
            )

        else:

            lines.append(
                f"⚠️ Budget dépassé de "
                f"{format_money(-budget['remaining'])}"
            )

    else:

        lines.append(
            "⚠️ Aucun budget global défini."
        )

    return {
        "text": "\n".join(lines),
        "link": {
            "url": "/dashboard",
            "label": "Voir mon dashboard"
        }
    }

# ---------------------------------------------------
# Route principale
# ---------------------------------------------------

@chatbot_bp.route("/chatbot/ask", methods=["POST"])
@login_required
def ask():

    data = request.get_json(silent=True) or {}

    topic = str(data.get("topic", "")).strip()
    message = str(data.get("message", "")).strip()[:300]

    if topic not in (
        "add",
        "budget",
        "stats",
        "save",
        "situation"
    ):
        topic = detect_topic(message) if message else "greeting"

    if topic == "greeting":

        reply = {
            "text": GREETING,
            "link": None
        }

    elif topic == "situation":

        reply = situation_reply(
            session["user_id"]
        )

    elif topic in REPLIES:

        reply = REPLIES[topic]

    else:

        reply = {
            "text": FALLBACK,
            "link": None
        }

    return jsonify(
        ok=True,
        topic=topic,
        reply=reply["text"],
        link=reply["link"]
    )