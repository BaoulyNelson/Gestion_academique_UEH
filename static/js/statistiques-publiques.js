document.addEventListener("DOMContentLoaded", () => {
    const elementDonnees = document.getElementById("donnees-statistiques");
    if (!elementDonnees || typeof Chart === "undefined") return;

    const donnees = JSON.parse(elementDonnees.textContent);
    Chart.defaults.font.family = '"Aptos", "Segoe UI", sans-serif';
    Chart.defaults.color = "#69758a";

    const afficherAbsence = (identifiant) => {
        const canevas = document.getElementById(identifiant);
        if (!canevas) return;
        canevas.hidden = true;
        const message = canevas.parentElement.querySelector(".graphe-vide");
        if (message) message.hidden = false;
    };

    const optionsCommunes = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 350 },
        plugins: {
            legend: { display: false },
            tooltip: { intersect: false },
        },
    };

    if (donnees.entites.valeurs.some((valeur) => valeur > 0)) {
        new Chart(document.getElementById("graphique-entites"), {
            type: "bar",
            data: {
                labels: donnees.entites.labels,
                datasets: [{
                    label: "Inscriptions",
                    data: donnees.entites.valeurs,
                    backgroundColor: donnees.entites.labels.map(
                        (_, index) => ["#3d7df2", "#24a978", "#e5a623", "#e85b63"][index % 4]
                    ),
                    borderRadius: 2,
                    maxBarThickness: 18,
                }],
            },
            options: {
                ...optionsCommunes,
                scales: {
                    x: { grid: { display: false }, ticks: { maxRotation: 55, minRotation: 35 } },
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#edf0f5" } },
                },
            },
        });
    } else {
        afficherAbsence("graphique-entites");
    }

    if (donnees.sexe.valeurs.some((valeur) => valeur > 0)) {
        new Chart(document.getElementById("graphique-sexe"), {
            type: "doughnut",
            data: {
                labels: donnees.sexe.labels,
                datasets: [{
                    data: donnees.sexe.valeurs,
                    backgroundColor: ["#e94c91", "#3d7df2", "#e5a623", "#cbd3df"],
                    borderColor: "#fff",
                    borderWidth: 3,
                    hoverOffset: 5,
                }],
            },
            options: {
                ...optionsCommunes,
                cutout: "62%",
                plugins: {
                    legend: { display: true, position: "bottom", labels: { boxWidth: 12, padding: 16 } },
                    tooltip: optionsCommunes.plugins.tooltip,
                },
            },
        });
    } else {
        afficherAbsence("graphique-sexe");
    }

    if (donnees.departements.valeurs.some((valeur) => valeur > 0)) {
        new Chart(document.getElementById("graphique-departements"), {
            type: "bar",
            data: {
                labels: donnees.departements.labels,
                datasets: [{
                    label: "Inscriptions",
                    data: donnees.departements.valeurs,
                    backgroundColor: ["#e94c55", "#f08024", "#f0bd22", "#56b778", "#2db875", "#67c6a1", "#277e72", "#13a888", "#12a5a8", "#4d9bdb", "#aeb8c8"],
                    borderRadius: 2,
                    barThickness: 13,
                }],
            },
            options: {
                ...optionsCommunes,
                indexAxis: "y",
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#edf0f5" } },
                    y: { grid: { display: false } },
                },
            },
        });
    } else {
        afficherAbsence("graphique-departements");
    }

    if (donnees.evolution.valeurs.some((valeur) => valeur > 0)) {
        new Chart(document.getElementById("graphique-evolution"), {
            type: "line",
            data: {
                labels: donnees.evolution.labels,
                datasets: [{
                    label: "Inscriptions quotidiennes",
                    data: donnees.evolution.valeurs,
                    borderColor: "#264d92",
                    backgroundColor: "#264d921a",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                }],
            },
            options: {
                ...optionsCommunes,
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 10, maxRotation: 45 } },
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#edf0f5" } },
                },
            },
        });
    } else {
        afficherAbsence("graphique-evolution");
    }
});