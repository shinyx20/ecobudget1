/* EcoBudget — page Objectifs d'épargne */
document.addEventListener("DOMContentLoaded", () => {
    const goalModal = document.getElementById("goal-modal");
    const contribModal = document.getElementById("contrib-modal");
    if (!goalModal || !contribModal) return;
    bindModal(goalModal);
    bindModal(contribModal);

    /* ---------- Créer / modifier un objectif ---------- */
    const gForm = document.getElementById("goal-form");
    const gTitle = document.getElementById("goal-title");
    const gId = document.getElementById("g-id");
    const gName = document.getElementById("g-name");
    const gTarget = document.getElementById("g-target");
    const gSaved = document.getElementById("g-saved");
    const gDeadline = document.getElementById("g-deadline");
    const gDesc = document.getElementById("g-description");
    const savedField = document.getElementById("saved-field");
    const gSubmit = document.getElementById("g-submit");
    const gFields = [gName, gTarget, gSaved, gDeadline, gDesc];

    function openGoal(d = null) {
        gFields.forEach((f) => setFieldError(f, ""));
        gId.value = d ? d.id : "";
        gName.value = d ? d.name : "";
        gTarget.value = d ? String(Number(d.target)) : "";
        gSaved.value = "";
        gDeadline.value = d ? d.deadline : "";
        gDeadline.min = d ? "" : goalModal.dataset.today;
        gDesc.value = d ? d.description : "";
        savedField.hidden = Boolean(d);   // le montant de départ n'existe qu'à la création
        gTitle.textContent = d ? "Modifier l'objectif" : "Nouvel objectif";
        gSubmit.textContent = d ? "Enregistrer les modifications" : "Enregistrer";
        openModalEl(goalModal, gName);
    }

    document.querySelectorAll(".js-open-goal").forEach((b) => b.addEventListener("click", () => openGoal()));
    document.querySelectorAll(".js-edit-goal").forEach((b) => b.addEventListener("click", () => openGoal(b.dataset)));
    gFields.forEach((f) => f.addEventListener("input", () => setFieldError(f, "")));

    function validateGoal() {
        let ok = true;
        const fail = (input, msg) => { setFieldError(input, msg); ok = false; };

        const name = gName.value.trim();
        if (!name) fail(gName, "Veuillez saisir le nom de l'objectif.");
        else if (name.length < 2) fail(gName, "Le nom doit contenir au moins 2 caractères.");

        const target = parseFloat(String(gTarget.value).replace(",", "."));
        if (!gTarget.value) fail(gTarget, "Veuillez saisir un montant cible.");
        else if (isNaN(target) || target <= 0) fail(gTarget, "Le montant doit être supérieur à 0.");

        if (!gId.value && gSaved.value) {
            const saved = parseFloat(String(gSaved.value).replace(",", "."));
            if (isNaN(saved) || saved < 0) fail(gSaved, "Montant invalide.");
            else if (!isNaN(target) && saved > target) fail(gSaved, "Le montant économisé ne peut pas dépasser la cible.");
        }
        if (!gDeadline.value) fail(gDeadline, "Veuillez choisir une date limite.");
        return ok;
    }

    gForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!validateGoal()) { toast("Veuillez corriger les champs en rouge.", "error"); return; }

        gSubmit.disabled = true;
        const res = await postJson("/goals/save", {
            id: gId.value,
            name: gName.value,
            target_amount: gTarget.value,
            saved_amount: gSaved.value,
            deadline: gDeadline.value,
            description: gDesc.value,
        });
        gSubmit.disabled = false;

        if (res.ok) { window.location.reload(); return; }
        const map = { name: gName, target_amount: gTarget, saved_amount: gSaved, deadline: gDeadline, description: gDesc };
        Object.entries(res.data.errors || {}).forEach(([k, msg]) => { if (map[k]) setFieldError(map[k], msg); });
        toast(res.data.message || "L'enregistrement a échoué. Vérifiez les champs.", "error");
    });

    /* ---------- Ajouter de l'argent ---------- */
    const cForm = document.getElementById("contrib-form");
    const cId = document.getElementById("c-id");
    const cAmount = document.getElementById("c-amount");
    const cInfo = document.getElementById("c-info");
    const cSubmit = document.getElementById("c-submit");

    document.querySelectorAll(".js-contribute").forEach((btn) =>
        btn.addEventListener("click", () => {
            setFieldError(cAmount, "");
            cId.value = btn.dataset.id;
            cAmount.value = "";
            cInfo.textContent = `Objectif : ${btn.dataset.name}`;
            openModalEl(contribModal, cAmount);
        })
    );
    cAmount.addEventListener("input", () => setFieldError(cAmount, ""));

    cForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const value = parseFloat(String(cAmount.value).replace(",", "."));
        if (!cAmount.value) { setFieldError(cAmount, "Veuillez saisir un montant."); return; }
        if (isNaN(value) || value <= 0) { setFieldError(cAmount, "Le montant doit être supérieur à 0."); return; }

        cSubmit.disabled = true;
        const res = await postJson(`/goals/${cId.value}/contribute`, { amount: cAmount.value });
        cSubmit.disabled = false;

        if (res.ok) { window.location.reload(); return; }
        if (res.data.errors && res.data.errors.amount) setFieldError(cAmount, res.data.errors.amount);
        toast(res.data.message || "Ajout impossible.", "error");
    });

    /* ---------- Supprimer ---------- */
    document.querySelectorAll(".js-delete-goal").forEach((btn) =>
        btn.addEventListener("click", () => {
            Swal.fire({
                title: "Supprimer cet objectif ?",
                text: `« ${btn.dataset.name} » et son historique de versements seront supprimés définitivement.`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Oui, supprimer",
                cancelButtonText: "Annuler",
                confirmButtonColor: "#E76F51",
                cancelButtonColor: "#6B7A80",
                focusCancel: true,
            }).then(async (result) => {
                if (!result.isConfirmed) return;
                const res = await postJson(`/goals/${btn.dataset.id}/delete`, {});
                if (res.ok) window.location.reload();
                else toast(res.data.message || "Suppression impossible.", "error");
            });
        })
    );
});