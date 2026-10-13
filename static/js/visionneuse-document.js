document.addEventListener("DOMContentLoaded", () => {
  const visionneuse = document.querySelector("#visionneuse-document");
  const cadre = visionneuse?.querySelector("[data-fichier-visionneuse]");
  const titre = visionneuse?.querySelector("[data-titre-visionneuse]");
  const telecharger = visionneuse?.querySelector("[data-telecharger-visionneuse]");
  if (!visionneuse || !cadre || !titre || !telecharger) return;

  let declencheur = null;
  let zoom = 1;
  let rotation = 0;

  const actualiserTransformation = () => {
    cadre.style.transform = `rotate(${rotation}deg) scale(${zoom})`;
  };

  const fermer = () => {
    visionneuse.hidden = true;
    document.body.classList.remove("visionneuse-ouverte");
    cadre.src = "about:blank";
    zoom = 1;
    rotation = 0;
    actualiserTransformation();
    declencheur?.focus({ preventScroll: true });
  };

  document.addEventListener("click", (evenement) => {
    const lien = evenement.target.closest("[data-apercu-document]");
    if (lien) {
      evenement.preventDefault();
      declencheur = lien;
      titre.textContent = lien.dataset.titreDocument || lien.textContent.trim();
      cadre.title = titre.textContent;
      cadre.src = lien.href;
      telecharger.href = lien.dataset.urlTelechargement || lien.href;
      telecharger.setAttribute("download", "");
      visionneuse.hidden = false;
      document.body.classList.add("visionneuse-ouverte");
      visionneuse.querySelector("[data-fermer-visionneuse]")?.focus({
        preventScroll: true,
      });
      return;
    }

    if (evenement.target.closest("[data-fermer-visionneuse]")) {
      fermer();
      return;
    }

    const outil = evenement.target.closest("[data-outil-document]")?.dataset
      .outilDocument;
    if (!outil || visionneuse.hidden) return;

    if (outil === "rotation-gauche") rotation -= 90;
    if (outil === "rotation-droite") rotation += 90;
    if (outil === "zoom-moins") zoom = Math.max(0.5, zoom - 0.1);
    if (outil === "zoom-plus") zoom = Math.min(3, zoom + 0.1);
    if (outil === "ajuster") {
      zoom = 1;
      rotation = 0;
    }
    if (outil === "plein-ecran") {
      if (document.fullscreenElement) document.exitFullscreen?.();
      else visionneuse.querySelector(".visionneuse-document-panneau")?.requestFullscreen?.();
    }
    actualiserTransformation();
  });

  document.addEventListener("keydown", (evenement) => {
    if (!visionneuse.hidden && evenement.key === "Escape") fermer();
  });
});