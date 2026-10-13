document.addEventListener("DOMContentLoaded", () => {
  const inscription = document.querySelector("#id_inscription");
  const urlMatieres = inscription?.dataset.urlMatieres;
  if (!inscription || !urlMatieres) return;

  const champsMatieres = () =>
    document.querySelectorAll('input[name^="epreuves-"][name$="-nom"]');

  const remplirChamp = (champ, groupes, selection = "") => {
    const identifiantListe = `${champ.id}-suggestions`;
    let liste = document.getElementById(identifiantListe);
    if (!liste) {
      liste = document.createElement("datalist");
      liste.id = identifiantListe;
      champ.insertAdjacentElement("afterend", liste);
      champ.setAttribute("list", identifiantListe);
    }
    liste.replaceChildren();
    const suggestions = new Map();
    groupes.forEach((groupe) => {
      groupe.matieres.forEach((matiere) => {
        if (!suggestions.has(matiere)) suggestions.set(matiere, new Set());
        suggestions.get(matiere).add(groupe.nom);
      });
    });
    suggestions.forEach((groupesNom, matiere) => {
      const option = document.createElement("option");
      option.value = matiere;
      option.label = [...groupesNom].join(" / ");
      liste.append(option);
    });
    if (selection) champ.value = selection;
  };

  const chargerMatieres = async (conserverSelections) => {
    const inscriptionId = inscription.value;
    const selections = [...champsMatieres()].map((champ) =>
      conserverSelections ? champ.value : "",
    );
    if (!inscriptionId) return;

    const url = new URL(urlMatieres, window.location.origin);
    url.searchParams.set("inscription", inscriptionId);
    try {
      const reponse = await fetch(url, {
        headers: { Accept: "application/json" },
      });
      if (!reponse.ok) throw new Error("Le chargement des matières a échoué.");
      const donnees = await reponse.json();
      [...champsMatieres()].forEach((champ, index) =>
        remplirChamp(champ, donnees.groupes, selections[index] || ""),
      );
    } catch {
      [...champsMatieres()].forEach((champ) => {
        remplirChamp(champ, []);
        champ.options[0].textContent = "Matières indisponibles";
      });
    }
  };

  const actualiserApresSelection = () => chargerMatieres(false);
  const jquery = window.django?.jQuery;
  if (jquery) {
    jquery(inscription).on("change select2:select", actualiserApresSelection);
    jquery(document).on("formset:added", () => chargerMatieres(true));
  } else {
    inscription.addEventListener("change", actualiserApresSelection);
    document.addEventListener("formset:added", () => chargerMatieres(true));
  }
  chargerMatieres(true);
});
