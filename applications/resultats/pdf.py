from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generer_pdf_ticket_resultat(resultat):
    epreuves = list(resultat.epreuves.all())
    contenu = BytesIO()
    largeur = 80 * mm
    hauteur = (128 + len(epreuves) * 13) * mm
    document = SimpleDocTemplate(
        contenu,
        pagesize=(largeur, hauteur),
        leftMargin=5 * mm,
        rightMargin=5 * mm,
        topMargin=6 * mm,
        bottomMargin=6 * mm,
        title=f"Résultat {resultat.inscription.numero_dossier}",
    )
    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        "TitreTicketResultat",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#10245d"),
    )
    style_centre = ParagraphStyle(
        "TexteCentreTicketResultat",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=7,
        leading=9,
    )
    style_cellule = ParagraphStyle(
        "CelluleTicketResultat",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=8,
    )
    inscription = resultat.inscription
    candidat = inscription.candidat.utilisateur
    moyenne = resultat.moyenne_calculee
    decision = "ADMIS" if resultat.admis_calcule else "NON ADMIS"
    date_publication = (
        resultat.date_publication.strftime("%d/%m/%Y à %H:%M")
        if resultat.date_publication
        else "Non renseignée"
    )

    elements = [
        Paragraph("UNIVERSITÉ D'ÉTAT D'HAÏTI", style_titre),
        Paragraph("RÉSULTAT DU CONCOURS", style_centre),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>DOSSIER #{escape(str(inscription.numero_dossier))}</b>", style_centre
        ),
        Spacer(1, 3 * mm),
    ]
    details = [
        ["Candidat", escape(candidat.get_full_name() or candidat.email)],
        ["Entité", escape(f"{inscription.entite.code} - {inscription.entite.nom}")],
        ["Option", escape(inscription.option.nom if inscription.option else "Aucune")],
        ["Année", escape(inscription.annee_academique)],
    ]
    tableau_details = Table(
        [
            [
                Paragraph(f"<b>{libelle}</b>", style_cellule),
                Paragraph(valeur, style_cellule),
            ]
            for libelle, valeur in details
        ],
        colWidths=[18 * mm, 52 * mm],
    )
    tableau_details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7dce5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.extend([tableau_details, Spacer(1, 3 * mm)])

    if epreuves:
        lignes_epreuves = [["Épreuve", "Note", "Barème", "Coeff."]]
        lignes_epreuves.extend(
            [
                Paragraph(escape(epreuve.nom), style_cellule),
                f"{epreuve.note:.2f}",
                f"{epreuve.bareme:.2f}",
                f"{epreuve.coefficient:.2f}",
            ]
            for epreuve in epreuves
        )
        lignes_epreuves.append(
            [
                Paragraph("<b>Total pondéré</b>", style_cellule),
                "",
                f"{resultat.bareme_pondere:.2f}",
                "",
            ]
        )
        tableau_epreuves = Table(
            lignes_epreuves,
            colWidths=[31 * mm, 13 * mm, 14 * mm, 12 * mm],
            repeatRows=1,
        )
        tableau_epreuves.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf0f5")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8cfdb")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.extend([tableau_epreuves, Spacer(1, 4 * mm)])

    moyenne_affichee = f"{moyenne:.2f} / 100" if moyenne is not None else "—"
    elements.extend(
        [
            Paragraph(f"<b>MOYENNE : {moyenne_affichee}</b>", style_titre),
            Spacer(1, 2 * mm),
            Paragraph(f"<b>DÉCISION : {decision}</b>", style_centre),
            Spacer(1, 4 * mm),
            Paragraph(f"Publié le {escape(date_publication)}", style_centre),
            Paragraph("Document officiel de consultation du résultat", style_centre),
        ]
    )
    document.build(elements)
    return contenu.getvalue()
