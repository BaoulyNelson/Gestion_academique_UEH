document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".avatar-photo").forEach((photo) => {
    const afficherPhoto = () => {
      photo.classList.add("est-chargee");
      const initiale = photo.parentElement.querySelector(".avatar-initial");
      if (initiale) initiale.hidden = true;
    };

    photo.addEventListener("load", afficherPhoto, { once: true });
    photo.addEventListener("error", () => photo.remove(), { once: true });
    if (photo.complete && photo.naturalWidth > 0) afficherPhoto();
  });
});