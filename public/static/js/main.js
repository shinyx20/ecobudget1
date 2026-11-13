/* EcoBudget — scripts communs à toutes les pages */

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const GREEN = "#20A889";
const GREY = "#6B7A80";

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initSidebar();
    initPasswordToggles();
    initFormValidation();
    initLogoutConfirm();
    initForgotPassword();
    initProgressBars();

    showFlashMessages();
    if (window.lucide) lucide.createIcons();
});

/* ---------- Notifications (toasts) ---------- */
function toast(message, type = "success") {
    Swal.fire({
        toast: true, position: "top-end", icon: type, title: message,
        showConfirmButton: false, timer: 4000, timerProgressBar: true,
    });
}

function showFlashMessages() {
    let messages = [];
    try { messages = JSON.parse(document.body.dataset.flash || "[]"); } catch (e) {}
    messages.forEach(([category, message]) => {
        const type = ["success", "error", "info", "warning"].includes(category) ? category : "info";
        toast(message, type);
    });
}
/* ---------- Mode clair / sombre ---------- */
/* ---------- Mode clair / sombre (mémorisé dans le compte) ---------- */
function initTheme() {
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            try { localStorage.setItem("eco-theme", next); } catch (e) {}
            if (document.body.dataset.auth === "1") postJson("/settings/theme", { theme: next });
        });
    });
}

/* ---------- Menu mobile ---------- */
function initSidebar() {
    const menuBtn = document.getElementById("menu-btn");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (!menuBtn) return;
    menuBtn.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
    if (backdrop) backdrop.addEventListener("click", () => document.body.classList.remove("sidebar-open"));
}

/* ---------- Afficher / masquer le mot de passe ---------- */
function initPasswordToggles() {
    document.querySelectorAll(".toggle-pass").forEach((btn) => {
        btn.addEventListener("click", () => {
            const input = btn.closest(".input-wrap").querySelector("input");
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            btn.classList.toggle("is-visible", show);
            btn.setAttribute("aria-label", show ? "Masquer le mot de passe" : "Afficher le mot de passe");
        });
    });
}

/* ---------- Validation des formulaires (côté client) ---------- */
function getErrorMessage(input) {
    const form = input.form;
    const value = input.type === "password" ? input.value : input.value.trim();

    if (input.required && !value) return "Ce champ est obligatoire.";
    if (!value) return "";

    if (input.type === "email" && !EMAIL_RE.test(value)) {
        return "Adresse email invalide (exemple : nom@mail.com).";
    }
    if (input.minLength > 0 && value.length < input.minLength) {
        return `Minimum ${input.minLength} caractères.`;
    }
    if (input.hasAttribute("data-strong") && !(/[A-Za-z]/.test(value) && /\d/.test(value))) {
        return "Le mot de passe doit contenir au moins une lettre et un chiffre.";
    }
    if (input.dataset.match) {
        const other = form.querySelector("#" + input.dataset.match);
        if (other && other.value !== input.value) return "Les mots de passe ne correspondent pas.";
    }
    return "";
}

function setFieldError(input, message) {
    const field = input.closest(".field");
    if (!field) return;
    const errorEl = field.querySelector(".field-error");
    if (errorEl) errorEl.textContent = message;
    field.classList.toggle("has-error", Boolean(message));
    input.setAttribute("aria-invalid", message ? "true" : "false");
}

function initFormValidation() {
    document.querySelectorAll("form[data-validate]").forEach((form) => {
        const inputs = form.querySelectorAll("input:not([type=hidden]):not([type=checkbox])");

        inputs.forEach((input) => {
            input.addEventListener("blur", () => setFieldError(input, getErrorMessage(input)));
            input.addEventListener("input", () => {
                // On efface l'erreur dès que l'utilisateur corrige
                if (input.closest(".field").classList.contains("has-error")) {
                    setFieldError(input, getErrorMessage(input));
                }
                // Si on modifie le mot de passe, on revérifie sa confirmation
                const dependent = form.querySelector(`[data-match="${input.id}"]`);
                if (dependent && dependent.value) setFieldError(dependent, getErrorMessage(dependent));
            });
        });

        form.addEventListener("submit", (event) => {
            let firstInvalid = null;
            inputs.forEach((input) => {
                const message = getErrorMessage(input);
                setFieldError(input, message);
                if (message && !firstInvalid) firstInvalid = input;
            });
            if (firstInvalid) {
                event.preventDefault();
                firstInvalid.focus();
                toast("Veuillez corriger les champs en rouge.", "error");
            }
        });
    });
}

/* ---------- Confirmation de déconnexion (contrôle explicite) ---------- */
function initLogoutConfirm() {
    const link = document.getElementById("logout-link");
    if (!link) return;
    link.addEventListener("click", (event) => {
        event.preventDefault();
        Swal.fire({
            title: "Se déconnecter ?",
            text: "Vous devrez vous reconnecter pour accéder à vos données.",
            icon: "question",
            showCancelButton: true,
            confirmButtonText: "Oui, me déconnecter",
            cancelButtonText: "Annuler",
            confirmButtonColor: GREEN,
            cancelButtonColor: GREY,
        }).then((result) => {
            if (result.isConfirmed) window.location.href = link.href;
        });
    });
}

/* ---------- Mot de passe oublié (simulé dans cette version) ---------- */
function initForgotPassword() {
    const link = document.getElementById("forgot-link");
    if (!link) return;
    link.addEventListener("click", (event) => {
        event.preventDefault();
        Swal.fire({
            title: "Mot de passe oublié ?",
            text: "Entrez votre adresse email pour recevoir un lien de réinitialisation.",
            input: "email",
            inputPlaceholder: "nom@mail.com",
            showCancelButton: true,
            confirmButtonText: "Envoyer le lien",
            cancelButtonText: "Annuler",
            confirmButtonColor: GREEN,
            cancelButtonColor: GREY,
            inputValidator: (value) => (!value ? "Veuillez saisir votre adresse email." : undefined),
        }).then((result) => {
            if (result.isConfirmed) {
                // Simulation : l'envoi réel d'email n'est pas implémenté dans ce projet.
                toast("Si cette adresse existe, un lien vient d'être envoyé.", "info");
            }
        });
    });
}
/* ---------- Barres de progression (animées) ---------- */
function initProgressBars() {
    const bars = document.querySelectorAll("[data-progress]");
    requestAnimationFrame(() => {
        bars.forEach((bar) => {
            const value = Math.max(0, Math.min(100, parseFloat(bar.dataset.progress) || 0));
            bar.style.width = value + "%";
        });
    });
}



/* ---------- Outils communs : fenêtres modales et requêtes JSON ---------- */
function openModalEl(modal, focusEl) {
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    if (focusEl) setTimeout(() => focusEl.focus(), 50);
}

function closeModalEl(modal) {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
}

/* Boutons [data-close], clic sur le fond et touche Échap ferment la modale */
function bindModal(modal) {
    modal.querySelectorAll("[data-close]").forEach((b) =>
        b.addEventListener("click", () => closeModalEl(modal))
    );
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModalEl(modal); });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal.classList.contains("open")) closeModalEl(modal);
    });
}

async function postJson(url, payload) {
    const meta = document.querySelector('meta[name="csrf-token"]');
    try {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": meta ? meta.content : "" },
            body: JSON.stringify(payload || {}),
        });
        let data = {};
        try { data = await res.json(); } catch (e) {}
        return { ok: res.ok && data.ok === true, data };
    } catch (e) {
        return { ok: false, data: { message: "Connexion impossible. Vérifiez que le serveur est lancé." } };
    }
}