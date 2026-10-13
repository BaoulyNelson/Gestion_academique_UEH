document.addEventListener("DOMContentLoaded", () => {
  const champPhoto = document.querySelector("input[data-apercu-photo-profil]");
  const apercu = document.querySelector("img[data-apercu-photo-profil]");

  if (!champPhoto || !apercu) return;

  let lecteurCourant = null;

  champPhoto.addEventListener("change", () => {
    const fichier = champPhoto.files?.[0];
    if (!fichier) return;
    const estImage =
      fichier.type.startsWith("image/") || /\.(jpe?g|png|webp)$/i.test(fichier.name);
    if (!estImage) return;

    lecteurCourant?.abort();
    const lecteur = new FileReader();
    lecteurCourant = lecteur;
    lecteur.addEventListener("load", () => {
      if (lecteurCourant === lecteur && typeof lecteur.result === "string") {
        apercu.src = lecteur.result;
      }
    });
    lecteur.readAsDataURL(fichier);
  });
});