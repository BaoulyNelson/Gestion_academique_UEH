document.addEventListener("DOMContentLoaded", () => {
  const formulaire = document.querySelector(".formulaire-inscription");
  if (!formulaire) return;

  const entite = formulaire.querySelector("#id_entite");
  const option = formulaire.querySelector("#id_option");
  const horaire = formulaire.querySelector("#id_horaire");
  const champAnnee = formulaire.querySelector("#id_annee_academique");
  const etatBrouillon = document.querySelector("#etat-brouillon");
  if (!entite || !option || !horaire) return;

  let minuterieBrouillon;
  const programmerSauvegarde = () => {
    window.clearTimeout(minuterieBrouillon);
    minuterieBrouillon = window.setTimeout(async () => {
      if (etatBrouillon) etatBrouillon.textContent = "Enregistrement du brouillon…";
      const jetonCsrf = formulaire.querySelector(
        "[name=csrfmiddlewaretoken]",
      )?.value;
      try {
        const reponse = await fetch(formulaire.dataset.urlBrouillon, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": jetonCsrf,
          },
          body: new FormData(formulaire),
        });
        if (!reponse.ok) throw new Error("La sauvegarde a échoué.");
        if (etatBrouillon) etatBrouillon.textContent = "Brouillon enregistré.";
      } catch {
        if (etatBrouillon)
          etatBrouillon.textContent =
            "Sauvegarde indisponible. Vos champs restent affichés.";
      }
    }, 500);
  };

  const remplirListe = (liste, elements, valeur, libelle, texteVide) => {
    liste.replaceChildren(new Option(texteVide, ""));
    elements.forEach((element) => {
      liste.add(new Option(element[libelle], element[valeur]));
    });
  };

  const chargerChoix = async (conserverSelection) => {
    const selectionOption = conserverSelection ? option.value : "";
    const selectionHoraire = conserverSelection ? horaire.value : "";
    if (!entite.value) {
      remplirListe(option, [], "id", "nom", "Choisissez d’abord une entité");
      remplirListe(horaire, [], "code", "nom", "N/A");
      return;
    }

    option.disabled = true;
    horaire.disabled = true;
    try {
      const url = new URL(formulaire.dataset.urlChoix, window.location.origin);
      url.searchParams.set("entite", entite.value);
      const reponse = await fetch(url, {
        headers: { Accept: "application/json" },
      });
      if (!reponse.ok) throw new Error("Le chargement des choix a échoué.");
      const donnees = await reponse.json();
      remplirListe(option, donnees.options, "id", "nom", "Aucune option");
      remplirListe(
        horaire,
        donnees.horaires,
        "code",
        "nom",
        "N/A",
      );
      option.value = selectionOption;
      horaire.value = selectionHoraire;
    } catch {
      remplirListe(option, [], "id", "nom", "Options indisponibles");
      remplirListe(horaire, [], "code", "nom", "N/A");
    } finally {
      option.disabled = false;
      horaire.disabled = false;
    }
  };

  entite.addEventListener("change", async () => {
    const conteneurEntite = entite.closest(".mb-3");
    conteneurEntite?.querySelectorAll(".invalid-feedback").forEach((erreur) => {
      erreur.remove();
    });
    entite.removeAttribute("aria-invalid");
    entite.classList.remove("is-invalid");
    await chargerChoix(false);
    programmerSauvegarde();
  });
  option.addEventListener("change", programmerSauvegarde);
  horaire.addEventListener("change", programmerSauvegarde);
  champAnnee?.addEventListener("change", programmerSauvegarde);
  champAnnee?.addEventListener("input", programmerSauvegarde);
  ["seq", "till", "date_depot"].forEach((nom) => {
    const champ = formulaire.querySelector(`[name="${nom}"]`);
    champ?.addEventListener("input", programmerSauvegarde);
    champ?.addEventListener("change", programmerSauvegarde);
  });
  formulaire
    .querySelector('[name="recu_paiement"]')
    ?.addEventListener("change", programmerSauvegarde);
  chargerChoix(true);
});
