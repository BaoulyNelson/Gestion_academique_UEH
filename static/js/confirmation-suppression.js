document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-confirmation-suppression]").forEach((formulaire) => {
        formulaire.addEventListener("submit", (evenement) => {
            const typeConfirmation = formulaire.dataset.confirmationSuppression;
            const suppressionSelectionnee = formulaire.querySelector(
                'input[name$="-DELETE"]:checked'
            );

            if (typeConfirmation === "formset" && !suppressionSelectionnee) return;

            const message = formulaire.dataset.messageConfirmation || "Confirmer la suppression ?";
            if (!window.confirm(message)) evenement.preventDefault();
        });
    });
});