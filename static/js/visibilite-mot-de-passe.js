document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[type="password"]').forEach((champ) => {
        if (champ.closest(".champ-mot-de-passe")) return;

        const conteneur = document.createElement("span");
        conteneur.className = "champ-mot-de-passe";
        champ.parentNode.insertBefore(conteneur, champ);
        conteneur.appendChild(champ);

        const bouton = document.createElement("button");
        bouton.type = "button";
        bouton.className = "bouton-visibilite-mot-de-passe";
        bouton.setAttribute("aria-label", "Afficher le mot de passe");
        bouton.setAttribute("aria-pressed", "false");
        bouton.title = "Afficher le mot de passe";
        bouton.innerHTML = '<i class="bi bi-eye" aria-hidden="true"></i>';
        conteneur.appendChild(bouton);

        bouton.addEventListener("click", () => {
            const afficher = champ.type === "password";
            const position = champ.selectionStart;
            champ.type = afficher ? "text" : "password";
            bouton.setAttribute("aria-pressed", String(afficher));
            bouton.setAttribute(
                "aria-label",
                afficher ? "Masquer le mot de passe" : "Afficher le mot de passe"
            );
            bouton.title = afficher
                ? "Masquer le mot de passe"
                : "Afficher le mot de passe";
            bouton.innerHTML = afficher
                ? '<i class="bi bi-eye-slash" aria-hidden="true"></i>'
                : '<i class="bi bi-eye" aria-hidden="true"></i>';
            champ.focus({ preventScroll: true });
            if (position !== null) champ.setSelectionRange(position, position);
        });
    });
});