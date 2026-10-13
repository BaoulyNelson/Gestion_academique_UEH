from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generer_pdf_inscription(inscription):
    contenu = BytesIO()
    document = SimpleDocTemplate(
        contenu,
        pagesize=A4,
        title=f"Dossier {inscription.numero_dossier}",
        leftMargin=45,
        rightMargin=45,
        topMargin=32,
        bottomMargin=38,
    )
    styles = getSampleStyleSheet()
    style_entete = ParagraphStyle(
        "EnteteOfficielle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
    )
    style_cellule = ParagraphStyle(
        "CelluleInscription", parent=styles["Normal"], fontSize=9, leading=12
    )
    candidat = inscription.candidat
    utilisateur = candidat.utilisateur
    logo = Image(finders.find("images/logo.png"), 44, 44, kind="proportional")
    blason = Image(finders.find("images/blason.png"), 58, 58, kind="proportional")
    entete = Table(
        [
            [logo, blason, ""],
            [
                Paragraph(
                    "UNIVERSITÉ D'ÉTAT D'HAÏTI<br/>"
                    "FICHE D'INSCRIPTION<br/>"
                    f"Année académique : {escape(inscription.annee_academique)}<br/>"
                    "21, Rue Rivière, B.P. 2279, Port-au-Prince, Haïti<br/>"
                    "Téléphones : (509) 3144-9479 / 31449404 / 31063804<br/>"
                    "admission@ueh.edu.ht",
                    style_entete,
                ),
                "",
                "",
            ],
        ],
        colWidths=[55, 395, 55],
    )
    entete.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (0, 1), (-1, 1)),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#0c1f5c")),
            ]
        )
    )
    adresse = " ".join(part for part in (candidat.adresse, candidat.ville) if part)
    identification = candidat.nif or candidat.ninu or "Non renseignée"
    lignes = [
        ["No Dossier", f"#{inscription.numero_dossier}"],
        ["Nom", escape(utilisateur.nom or "")],
        ["Prénom", escape(utilisateur.prenom or "")],
        [
            "Date de naissance",
            (
                candidat.date_naissance.strftime("%d-%m-%Y")
                if candidat.date_naissance
                else "Non renseignée"
            ),
        ],
        ["Sexe", escape(candidat.get_sexe_display() or "Non renseigné")],
        ["Identification", escape(identification)],
        ["Nationalité", escape(candidat.nationalite or "Non renseignée")],
        ["Adresse", escape(adresse or "Non renseignée")],
        ["Email", escape(utilisateur.email)],
        ["Contact", escape(candidat.telephone or "Non renseigné")],
        [
            "Candidat",
            escape(utilisateur.get_full_name() or utilisateur.email),
        ],
        ["Entité", escape(str(inscription.entite))],
        ["Option", escape(inscription.option.nom if inscription.option else "Aucune")],
        ["Année académique", escape(inscription.annee_academique)],
        ["Vacation", escape(inscription.horaire or "N/A")],
        ["Seq", escape(inscription.seq or "Non renseigné")],
        ["Till", escape(inscription.till or "Non renseigné")],
        [
            "Date de dépôt",
            (
                inscription.date_depot.strftime("%d-%m-%Y")
                if inscription.date_depot
                else "Non renseignée"
            ),
        ],
        [
            "Salle",
            escape(
                inscription.salle.nom
                if inscription.salle
                else "En attente d'affectation"
            ),
        ],
        ["Statut", escape(inscription.get_statut_display())],
        ["Date d'inscription", inscription.date_inscription.strftime("%d/%m/%Y %H:%M")],
    ]
    tableau = Table(
        [
            [
                Paragraph(f"<b>{escape(str(libelle))}</b>", style_cellule),
                Paragraph(escape(str(valeur)), style_cellule),
            ]
            for libelle, valeur in lignes
        ],
        colWidths=[145, 360],
    )
    tableau.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf0f5")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#17233c")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8cfdb")),
                ("PADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    document.build([entete, Spacer(1, 18), tableau])
    return contenu.getvalue()
