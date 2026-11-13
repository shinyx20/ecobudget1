/* EcoBudget — gestion des transactions (modale + CRUD) */

document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("tx-modal");
    if (!modal) return;

    const form = document.getElementById("tx-form");
    const title = document.getElementById("modal-title");
    const idInput = document.getElementById("tx-id");
    const amount = document.getElementById("tx-amount");
    const category = document.getElementById("tx-category");
    const date = document.getElementById("tx-date");
    const description = document.getElementById("tx-description");
    const submitBtn = document.getElementById("tx-submit");
    const categories = JSON.parse(modal.dataset.categories || "[]");
    const csrf = document.querySelector('meta[name="csrf-token"]').content;

    const fields = [amount, category, date, description];

    /* ---------- Utilitaires ---------- */
    function todayLocal() {
        const d = new Date();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${d.getFullYear()}-${m}-${day}`;
    }

    function currentType() {
        return form.querySelector('input[name="type"]:checked').value;
    }

    function fillCategories(type, selectedId) {
        category.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choisir une catégorie";
        category.appendChild(placeholder);

        categories.filter((c) => c.type === type).forEach((c) => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = c.name;
            if (String(c.id) === String(selectedId)) opt.selected = true;
            category.appendChild(opt);
        });
    }

    function clearErrors() {
        fields.forEach((f) => setFieldError(f, ""));
    }

    /* ---------- Ouverture / fermeture ---------- */
    function openModal({ id = "", type = "expense", amountValue = "", categoryId = "",
                         dateValue = todayLocal(), descriptionValue = "" } = {}) {
        clearErrors();
        idInput.value = id;
        form.querySelector(`input[name="type"][value="${type}"]`).checked = true;
        amount.value = amountValue;
        date.value = dateValue;
        description.value = descriptionValue;
        fillCategories(type, categoryId);

        title.textContent = id ? "Modifier la transaction" : "Ajouter une transaction";
        submitBtn.textContent = id ? "Enregistrer les modifications" : "Enregistrer";

        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-open");
        setTimeout(() => amount.focus(), 50);
    }

    function closeModal() {
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-open");
    }

    document.querySelectorAll(".js-open-add").forEach((btn) =>
        btn.addEventListener("click", () => openModal())
    );

    document.querySelectorAll(".js-edit").forEach((btn) =>
        btn.addEventListener("click", () => {
            const d = btn.dataset;
            openModal({
                id: d.id,
                type: d.type,
                amountValue: String(Number(d.amount)),
                categoryId: d.category,
                dateValue: d.date,
                descriptionValue: d.description,
            });
        })
    );

    modal.querySelectorAll("[data-close]").forEach((btn) => btn.addEventListener("click", closeModal));
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal.classList.contains("open")) closeModal();
    });

    /* Changer de type => catégories adaptées (dépenses ou revenus) */
    form.querySelectorAll('input[name="type"]').forEach((radio) =>
        radio.addEventListener("change", () => {
            fillCategories(currentType(), "");
            setFieldError(category, "");
        })
    );

    /* Effacer l'erreur d'un champ dès qu'on le corrige */
    fields.forEach((f) =>
        f.addEventListener("input", () => setFieldError(f, ""))
    );

    /* ---------- Validation côté client ---------- */
    function validate() {
        let ok = true;
        const fail = (input, msg) => { setFieldError(input, msg); ok = false; };

        const value = parseFloat(String(amount.value).replace(",", "."));
        if (!amount.value) fail(amount, "Veuillez saisir un montant.");
        else if (isNaN(value) || value <= 0) fail(amount, "Le montant doit être supérieur à 0.");

        if (!category.value) fail(category, "Veuillez choisir une catégorie.");
        if (!date.value) fail(date, "Veuillez choisir une date.");
        if (description.value.length > 200) fail(description, "La description est limitée à 200 caractères.");

        return ok;
    }

    /* ---------- Envoi au serveur ---------- */
    async function post(url, payload) {
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                body: JSON.stringify(payload),
            });
            let data = {};
            try { data = await res.json(); } catch (e) {}
            return { ok: res.ok && data.ok === true, data };
        } catch (e) {
            return { ok: false, data: { message: "Connexion impossible. Vérifiez que le serveur est lancé." } };
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!validate()) {
            toast("Veuillez corriger les champs en rouge.", "error");
            return;
        }

        const id = idInput.value;
        const url = id ? `/transactions/${id}/edit` : "/transactions/add";
        const payload = {
            type: currentType(),
            amount: amount.value,
            category_id: category.value,
            date: date.value,
            description: description.value,
        };

        submitBtn.disabled = true;
        const result = await post(url, payload);
        submitBtn.disabled = false;

        if (result.ok) {
            window.location.reload(); // le message de succès est affiché après rechargement
            return;
        }

        // Erreurs renvoyées par le serveur : on les affiche sous les champs
        const errors = result.data.errors || {};
        const map = { amount, category_id: category, date, description };
        Object.entries(errors).forEach(([name, msg]) => {
            if (map[name]) setFieldError(map[name], msg);
        });
        toast(result.data.message || "L'enregistrement a échoué. Vérifiez les champs.", "error");
    });

    /* ---------- Suppression avec confirmation ---------- */
    document.querySelectorAll(".js-delete").forEach((btn) =>
        btn.addEventListener("click", () => {
            const d = btn.dataset;
            Swal.fire({
                title: "Supprimer cette transaction ?",
                text: `${d.description} — ${d.amount}. Cette action est définitive.`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Oui, supprimer",
                cancelButtonText: "Annuler",
                confirmButtonColor: "#E76F51",
                cancelButtonColor: "#6B7A80",
                focusCancel: true,
            }).then(async (result) => {
                if (!result.isConfirmed) return;
                const res = await post(`/transactions/${d.id}/delete`, {});
                if (res.ok) window.location.reload();
                else toast(res.data.message || "Suppression impossible.", "error");
            });
        })
    );
});