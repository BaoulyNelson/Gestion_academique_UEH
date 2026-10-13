document.addEventListener("DOMContentLoaded", () => {
  const entite = document.querySelector("#id_entite");
  const lienAjoutSalle = document.querySelector("#add_id_salle");
  if (!entite || !lienAjoutSalle) return;

  const transmettreEntite = () => {
    const url = new URL(lienAjoutSalle.href, window.location.origin);
    if (entite.value) url.searchParams.set("entite", entite.value);
    else url.searchParams.delete("entite");
    lienAjoutSalle.href = url.toString();
  };

  entite.addEventListener("change", transmettreEntite);
  lienAjoutSalle.addEventListener("click", transmettreEntite);
  transmettreEntite();
});
