document.addEventListener("DOMContentLoaded", () => {
    const vueRubriques = {
        accueil: "accueil",
        guide_public: "guide",
        entites_publiques: "entites",
        statistiques_publiques: "statistiques",
        a_propos_public: "a_propos",
        guide_documents: "guide",
        mon_profil: "profil",
        mes_documents: "documents",
        mes_inscriptions: "inscriptions",
        nouvelle_inscription: "inscriptions",
        creer: "inscriptions",
        detail: "inscriptions",
        liste_inscriptions: "inscriptions",
        liste_salles: "salles",
        liste_options: "options",
        liste_horaires: "horaires",
        gerer_resultat: "resultats",
        modifier_candidat: "resultats",
        journal_actions: "journal",
        recu: "inscriptions",
        pdf: "inscriptions",
        mes_resultats: "resultats",
    };
    const rubriqueActive = vueRubriques[document.body.dataset.view];
    if (rubriqueActive) {
        document.querySelectorAll("[data-navigation]").forEach((lien) => {
            if (lien.dataset.navigation === rubriqueActive) {
                lien.setAttribute("aria-current", "page");
            } else {
                lien.removeAttribute("aria-current");
            }
        });
    }

    const liensAncres = [...document.querySelectorAll('a[href^="#"]')];
    const activerLien = (cible) => {
        liensAncres.forEach((lien) => {
            const actif = lien.getAttribute("href") === cible;
            lien.classList.toggle("active", actif);
            if (actif) lien.setAttribute("aria-current", "location");
            else lien.removeAttribute("aria-current");
        });
    };

    if (liensAncres.length) {
        activerLien(window.location.hash || "#accueil");
        liensAncres.forEach((lien) => {
            lien.addEventListener("click", () => {
                activerLien(lien.getAttribute("href"));
            });
        });
    }

    const declencheur = document.querySelector("[data-ouvrir-plus]");
    const panneau = document.getElementById("panneau-plus");
    const voile = document.querySelector(".voile-plus");
    if (!declencheur || !panneau || !voile) return;

    let elementAvantOuverture = null;
    let minuterieFermeture = null;

    const fermer = () => {
        if (panneau.hidden) return;
        panneau.classList.remove("est-ouvert");
        voile.classList.remove("est-ouvert");
        declencheur.setAttribute("aria-expanded", "false");
        document.body.classList.remove("menu-plus-ouvert");
        window.clearTimeout(minuterieFermeture);
        minuterieFermeture = window.setTimeout(() => {
            panneau.hidden = true;
            voile.hidden = true;
        }, 230);
        (elementAvantOuverture || declencheur).focus({ preventScroll: true });
    };

    const ouvrir = () => {
        window.clearTimeout(minuterieFermeture);
        elementAvantOuverture = document.activeElement;
        panneau.hidden = false;
        voile.hidden = false;
        declencheur.setAttribute("aria-expanded", "true");
        document.body.classList.add("menu-plus-ouvert");
        window.requestAnimationFrame(() => {
            panneau.classList.add("est-ouvert");
            voile.classList.add("est-ouvert");
            panneau.querySelector("[data-fermer-plus]").focus({ preventScroll: true });
        });
    };

    declencheur.addEventListener("click", ouvrir);
    voile.addEventListener("click", fermer);
    panneau.querySelectorAll("[data-fermer-plus]").forEach((bouton) => {
        bouton.addEventListener("click", fermer);
    });
    panneau.querySelectorAll("[data-fermer-plus-lien]").forEach((lien) => {
        lien.addEventListener("click", fermer);
    });
    panneau.querySelectorAll("a[href^='/']").forEach((lien) => {
        lien.addEventListener("click", fermer);
    });

    document.addEventListener("keydown", (evenement) => {
        if (panneau.hidden) return;
        if (evenement.key === "Escape") {
            evenement.preventDefault();
            fermer();
            return;
        }
        if (evenement.key !== "Tab") return;

        const elements = [...panneau.querySelectorAll("a[href], button:not([disabled])")];
        if (!elements.length) return;
        const premier = elements[0];
        const dernier = elements[elements.length - 1];
        if (evenement.shiftKey && document.activeElement === premier) {
            evenement.preventDefault();
            dernier.focus();
        } else if (!evenement.shiftKey && document.activeElement === dernier) {
            evenement.preventDefault();
            premier.focus();
        }
    });
});