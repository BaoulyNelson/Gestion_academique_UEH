document.addEventListener("DOMContentLoaded", () => {
    const formulaire = document.querySelector(".auth-page-focus");
    if (!formulaire) return;

    const champEmail = formulaire.querySelector(
        'input[type="email"], input[autocomplete="email"]'
    );
    if (champEmail) champEmail.focus({ preventScroll: true });
});