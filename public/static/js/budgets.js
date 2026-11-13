/* EcoBudget — page Budgets */
document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("budget-modal");
    if (!modal) return;
    bindModal(modal);

    const form = document.getElementById("budget-form");
    const title = document.getElementById("budget-title");
    const category = document.getElementById("b-category");
    const amount = document.getElementById("b-amount");
    const submitBtn = document.getElementById("b-submit");
    const month = modal.dataset.month;

    function open(cat = "", amountValue = "", lock = false) {
        setFieldError(category, "");
        setFieldError(amount, "");
        category.value = cat;
        category.disabled = lock;   // en modification, on ne change pas la catégorie
        amount.value = amountValue;
        title.textContent = lock ? "Modifier le budget" : "Définir un budget";
        openModalEl(modal, amount);
    }

    document.querySelectorAll(".js-open-budget").forEach((btn) =>
        btn.addEventListener("click", () => open())
    );
    document.querySelectorAll(".js-edit-budget").forEach((btn) =>
        btn.addEventListener("click", () =>
            open(btn.dataset.category, String(Number(btn.dataset.amount)), true)
        )
    );

    amount.addEventListener("input", () => setFieldError(amount, ""));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const value = parseFloat(String(amount.value).replace(",", "."));
        if (!amount.value) { setFieldError(amount, "Veuillez saisir un montant."); return; }
        if (isNaN(value) || value <= 0) { setFieldError(amount, "Le montant doit être supérieur à 0."); return; }

        submitBtn.disabled = true;
        const res = await postJson("/budgets/save", {
            month: month,
            category_id: category.value || null,
            amount: amount.value,
        });
        submitBtn.disabled = false;

        if (res.ok) { window.location.reload(); return; }
        const errors = res.data.errors || {};
        if (errors.amount) setFieldError(amount, errors.amount);
        if (errors.category_id) setFieldError(category, errors.category_id);
        toast(res.data.message || "L'enregistrement a échoué. Vérifiez les champs.", "error");
    });

    document.querySelectorAll(".js-delete-budget").forEach((btn) =>
        btn.addEventListener("click", () => {
            Swal.fire({
                title: "Supprimer ce budget ?",
                text: `Vous allez supprimer ${btn.dataset.name}. Vos dépenses ne seront pas touchées.`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Oui, supprimer",
                cancelButtonText: "Annuler",
                confirmButtonColor: "#E76F51",
                cancelButtonColor: "#6B7A80",
                focusCancel: true,
            }).then(async (result) => {
                if (!result.isConfirmed) return;
                const res = await postJson(`/budgets/${btn.dataset.id}/delete`, {});
                if (res.ok) window.location.reload();
                else toast(res.data.message || "Suppression impossible.", "error");
            });
        })
    );

    const copyBtn = document.getElementById("copy-prev");
    if (copyBtn) {
        copyBtn.addEventListener("click", async () => {
            const res = await postJson("/budgets/copy", { month: month });
            if (res.ok) window.location.reload();
            else toast(res.data.message || "Copie impossible.", "error");
        });
    }
});