from io import BytesIO

from django.utils.html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from applications.pdf_documents import (
    GRIS,
    LIGNE,
    VERT,
    entete_pied_pdf,
    signature_pdf,
)

from .models import PaiementScolarite
from .services.paiements import montant_scolarite_confirme


def generer_recu_paiement_pdf(paiement: PaiementScolarite) -> bytes:
    tampon = BytesIO()
    reference = paiement.reference
    pied_de_page, configuration = entete_pied_pdf("Recu de paiement", reference)
    document = SimpleDocTemplate(
        tampon,
        pagesize=letter,
        rightMargin=0.8 * inch,
        leftMargin=0.8 * inch,
        topMargin=1.2 * inch,
        bottomMargin=0.8 * inch,
        title=f"Recu de scolarite - {reference}",
        author=configuration.nom_site,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RecuTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=24,
        alignment=1,
        textColor=VERT,
        spaceBefore=28,
        spaceAfter=22,
    )
    cell_style = ParagraphStyle(
        "RecuCell",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
    )
    nom = paiement.etudiant.get_full_name() or paiement.etudiant.username
    code = getattr(paiement.etudiant, "profil_etudiant", None)
    code = getattr(code, "code_etudiant", None) or "Non attribue"
    total = montant_scolarite_confirme(paiement.etudiant, paiement.tarif)
    reste = max(paiement.tarif.montant - total, 0)
    donnees = (
        ("Recu numero", paiement.reference),
        ("Etudiant", nom),
        ("Code etudiant", code),
        ("Entite", paiement.tarif.programme.entite.nom),
        ("Programme", paiement.tarif.programme.nom),
        (
            "Periode",
            f"{paiement.tarif.periode.nom} - {paiement.tarif.periode.annee_academique}",
        ),
        ("Date du versement", paiement.date_paiement.strftime("%d/%m/%Y")),
        ("Montant recu", f"{paiement.montant:,.2f} {paiement.tarif.devise}"),
        ("Total confirme", f"{total:,.2f} {paiement.tarif.devise}"),
        ("Montant du tarif", f"{paiement.tarif.montant:,.2f} {paiement.tarif.devise}"),
        ("Solde restant", f"{reste:,.2f} {paiement.tarif.devise}"),
        (
            "Valide par",
            paiement.valide_par.get_full_name() or paiement.valide_par.username,
        ),
        (
            "Date de validation",
            (
                paiement.date_validation.strftime("%d/%m/%Y %H:%M")
                if paiement.date_validation
                else "-"
            ),
        ),
    )
    lignes = [
        [
            Paragraph(escape(libelle), cell_style),
            Paragraph(escape(valeur), cell_style),
        ]
        for libelle, valeur in donnees
    ]
    tableau = Table(lignes, colWidths=(1.8 * inch, 4.9 * inch))
    tableau.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, LIGNE),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story = [
        Paragraph(escape(paiement.tarif.programme.entite.nom), styles["Normal"]),
        Paragraph("RECU DE PAIEMENT DE SCOLARITE", title_style),
        Paragraph(
            "Le Registrariat confirme la reception et la validation du versement indique ci-dessous.",
            styles["BodyText"],
        ),
        Spacer(1, 0.25 * inch),
        tableau,
        Spacer(1, 0.45 * inch),
        Table(
            [
                ["", Paragraph("Pour le Registrariat", cell_style)],
                ["", signature_pdf()],
                [
                    "",
                    Paragraph(
                        escape(
                            paiement.valide_par.get_full_name()
                            or paiement.valide_par.username
                        ),
                        cell_style,
                    ),
                ],
                ["", Paragraph("Signature et sceau", cell_style)],
            ],
            colWidths=(3.35 * inch, 3.35 * inch),
            style=TableStyle(
                [
                    ("ALIGN", (1, 0), (1, -1), "CENTER"),
                    ("LINEABOVE", (1, 2), (1, 2), 0.7, GRIS),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            ),
        ),
    ]

    document.build(story, onFirstPage=pied_de_page, onLaterPages=pied_de_page)
    return tampon.getvalue()
