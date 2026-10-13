document.addEventListener("DOMContentLoaded", () => {
  const formulaire = document.querySelector("[data-profil-etape]");
  if (!formulaire) return;

  const identifiantNif = formulaire.querySelector("#id_nif");
  const identifiantNinu = formulaire.querySelector("#id_ninu");
  const fichierNif = formulaire.querySelector('[data-fichier-identifiant="nif"]');
  const fichierNinu = formulaire.querySelector('[data-fichier-identifiant="ninu"]');

  const formaterNif = () => {
    if (!identifiantNif) return;
    const positionCurseur = identifiantNif.selectionStart ?? identifiantNif.value.length;
    const chiffresAvantCurseur = identifiantNif.value
      .slice(0, positionCurseur)
      .replace(/\D/g, "").length;
    const chiffres = identifiantNif.value.replace(/\D/g, "").slice(0, 10);
    const valeur = [chiffres.slice(0, 3), chiffres.slice(3, 6), chiffres.slice(6, 9), chiffres.slice(9, 10)]
      .filter(Boolean)
      .join("-");
    identifiantNif.value = valeur;

    let nouveauCurseur = 0;
    let chiffresComptes = 0;
    while (nouveauCurseur < valeur.length && chiffresComptes < chiffresAvantCurseur) {
      if (/\d/.test(valeur[nouveauCurseur])) chiffresComptes += 1;
      nouveauCurseur += 1;
    }
    if (valeur[nouveauCurseur] === "-") nouveauCurseur += 1;
    identifiantNif.setSelectionRange(nouveauCurseur, nouveauCurseur);
  };

  identifiantNif?.addEventListener("input", formaterNif);
  formaterNif();

  const mettreAJourPiecesIdentite = () => {
    if (!identifiantNif || !identifiantNinu || !fichierNif || !fichierNinu) return;

    const nif = identifiantNif.value.trim();
    const ninu = identifiantNinu.value.trim();
    if (nif && ninu) {
      if (document.activeElement === identifiantNif) identifiantNinu.value = "";
      else identifiantNif.value = "";
    }

    const identifiantActif = identifiantNif.value.trim() ? "nif" : identifiantNinu.value.trim() ? "ninu" : "aucun";
    [fichierNif, fichierNinu].forEach((conteneur) => {
      const estNif = conteneur.dataset.fichierIdentifiant === "nif";
      const visible = identifiantActif === "aucun" || (identifiantActif === "nif") === estNif;
      const champ = conteneur.querySelector('input[type="file"]');
      conteneur.hidden = !visible;
      if (champ) {
        champ.disabled = !visible;
        champ.required = visible && identifiantActif !== "aucun" && conteneur.dataset.dejaDepose !== "true";
        if (!visible) champ.value = "";
      }
    });
  };

  identifiantNif?.addEventListener("input", mettreAJourPiecesIdentite);
  identifiantNinu?.addEventListener("input", mettreAJourPiecesIdentite);
  mettreAJourPiecesIdentite();

  const departement = formulaire.querySelector("#id_departement_geographique");
  const commune = formulaire.querySelector("#id_ville");
  if (!departement || !commune || !formulaire.dataset.urlCommunes) return;

  departement.addEventListener("change", async () => {
    const selectionPrecedente = commune.value;
    commune.disabled = true;
    try {
      const url = new URL(formulaire.dataset.urlCommunes, window.location.origin);
      url.searchParams.set("departement", departement.value);
      const reponse = await fetch(url, { headers: { Accept: "application/json" } });
      if (!reponse.ok) throw new Error("Le chargement des communes a échoué.");
      const donnees = await reponse.json();
      commune.replaceChildren(
        ...donnees.communes.map((choix) => new Option(choix.label, choix.value)),
      );
      if (donnees.communes.some((choix) => choix.value === selectionPrecedente)) {
        commune.value = selectionPrecedente;
      }
    } catch {
      commune.replaceChildren(new Option("Communes indisponibles", ""));
    } finally {
      commune.disabled = !departement.value;
    }
  });
});