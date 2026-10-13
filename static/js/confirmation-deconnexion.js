document.addEventListener("DOMContentLoaded", () => {
    const elementModal = document.getElementById("modal-confirmation-deconnexion");
    const boutonConfirmer = document.getElementById("confirmer-deconnexion");
    if (!elementModal || !boutonConfirmer || !window.bootstrap) return;

    const modal = window.bootstrap.Modal.getOrCreateInstance(elementModal);
    let formulaireEnAttente = null;

    document.querySelectorAll("form[data-confirmation-deconnexion]").forEach((formulaire) => {
        formulaire.addEventListener("submit", (evenement) => {
            if (formulaire.dataset.deconnexionConfirmee === "oui") {
                delete formulaire.dataset.deconnexionConfirmee;
                return;
            }
            evenement.preventDefault();
            formulaireEnAttente = formulaire;
            modal.show();
        });
    });

    boutonConfirmer.addEventListener("click", () => {
        if (!formulaireEnAttente) return;
        const formulaire = formulaireEnAttente;
        formulaireEnAttente = null;
        formulaire.dataset.deconnexionConfirmee = "oui";
        modal.hide();
        formulaire.requestSubmit();
    });

    elementModal.addEventListener("hidden.bs.modal", () => {
        formulaireEnAttente = null;
    });
});