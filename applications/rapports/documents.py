from collections import defaultdict
from io import BytesIO

from django.utils.html import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from applications.pdf_documents import (
    VERT,
    GRIS,
    LIGNE,
    entete_pied_pdf,
    signature_pdf,
)
from applications.notes.models import Evaluation
from applications.notes.services.resultats import calculer_moyenne_ponderee

from .models import ActeAcademique
from .models import SoutenanceMemoire


def obtenir_resultats_releve(acte):
    evaluations = (
        Evaluation.objects.filter(
            etudiant=acte.etudiant,
            cours__programme=acte.programme,
            periode=acte.periode,
            est_publiee=True,
        )
        .select_related("cours")
        .order_by("cours__code", "libelle")
    )
    groupes = defaultdict(list)
    for evaluation in evaluations:
        groupes[evaluation.cours_id].append(evaluation)

    return [
        {
            "cours": evaluations_cours[0].cours,
            "evaluations": evaluations_cours,
            "moyenne": calculer_moyenne_ponderee(evaluations_cours),
        }
        for evaluations_cours in groupes.values()
    ]


def _paragraph(texte, style):
    return Paragraph(escape(str(texte)), style)


def _texte_acte(acte):
    nom = acte.etudiant.get_full_name() or acte.etudiant.username
    programme = acte.programme.nom
    periode = f"{acte.periode.nom} ({acte.periode.annee_academique})"

    if acte.type_acte == ActeAcademique.TypeActe.ATTESTATION_INSCRIPTION:
        return (
            f"Le Registrariat atteste que <b>{escape(nom)}</b> est inscrit au "
            f"programme <b>{escape(programme)}</b> pour la periode "
            f"<b>{escape(periode)}</b>. L'inscription pedagogique correspondante "
            "a ete validee par l'entite."
        )
    if acte.type_acte == ActeAcademique.TypeActe.ATTESTATION_ETUDES:
        return (
            f"Le Registrariat atteste que le dossier academique de "
            f"<b>{escape(nom)}</b> comporte des resultats publies au programme "
            f"<b>{escape(programme)}</b> pour la periode <b>{escape(periode)}</b>."
        )
    if acte.type_acte == ActeAcademique.TypeActe.CERTIFICAT:
        return (
            f"Le present certificat est delivre a <b>{escape(nom)}</b> et concerne "
            f"son dossier d'etudes au programme <b>{escape(programme)}</b>, pour "
            f"la periode <b>{escape(periode)}</b>."
        )
    if acte.type_acte == ActeAcademique.TypeActe.DIPLOME:
        return (
            f"Le Registrariat certifie que le dossier d'etudes de "
            f"<b>{escape(nom)}</b> au programme <b>{escape(programme)}</b> a ete "
            "reconnu au statut diplome par l'entite. Le present acte est delivre "
            "sous reserve des reglements academiques applicables."
        )
    return (
        f"Le present releve concerne les resultats publies de "
        f"<b>{escape(nom)}</b> au programme <b>{escape(programme)}</b> pour la "
        f"periode <b>{escape(periode)}</b>. Seules les notes publiees par le "
        "Registrariat sont reproduites ci-dessous."
    )


def generer_pdf_acte(acte):
    tampon = BytesIO()
    reference = acte.reference
    pied_de_page, configuration = entete_pied_pdf("Acte academique", reference)
    document = SimpleDocTemplate(
        tampon,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1.2 * inch,
        bottomMargin=0.8 * inch,
        title=f"{acte.get_type_acte_display()} - {reference}",
        author=configuration.nom_site,
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    entity_style = ParagraphStyle(
        "Entite",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=GRIS,
    )
    title_style = ParagraphStyle(
        "ActeTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=22,
        alignment=TA_CENTER,
        textColor=VERT,
        spaceBefore=22,
        spaceAfter=18,
    )
    body_style = ParagraphStyle(
        "ActeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=18,
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "ActeSection",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=VERT,
        spaceBefore=14,
        spaceAfter=8,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
    )
    header_cell_style = ParagraphStyle(
        "TableHeader",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    story = []

    story.extend(
        [
            _paragraph(acte.programme.entite.nom, entity_style),
            Spacer(1, 0.18 * inch),
            _paragraph(acte.get_type_acte_display().upper(), title_style),
            Paragraph(_texte_acte(acte), body_style),
        ]
    )

    if acte.type_acte == ActeAcademique.TypeActe.RELEVE_NOTES:
        resultats = obtenir_resultats_releve(acte)
        story.append(_paragraph("Resultats publies", section_style))
        lignes = [
            [
                _paragraph("Cours", header_cell_style),
                _paragraph("Evaluation", header_cell_style),
                _paragraph("Note / 100", header_cell_style),
                _paragraph("Coefficient", header_cell_style),
            ]
        ]
        for resultat in resultats:
            cours = resultat["cours"]
            for index, evaluation in enumerate(resultat["evaluations"]):
                lignes.append(
                    [
                        _paragraph(
                            (
                                f"{escape(cours.code)} - {escape(cours.nom)}"
                                if index == 0
                                else ""
                            ),
                            cell_style,
                        ),
                        _paragraph(evaluation.libelle, cell_style),
                        _paragraph(evaluation.note, cell_style),
                        _paragraph(evaluation.coefficient, cell_style),
                    ]
                )
            lignes.append(
                [
                    "",
                    _paragraph("Moyenne ponderee du cours", cell_style),
                    _paragraph(resultat["moyenne"], cell_style),
                    "",
                ]
            )
        if not resultats:
            lignes.append(
                [_paragraph("Aucun resultat publie.", cell_style), "", "", ""]
            )
        tableau = Table(
            lignes,
            colWidths=(2.25 * inch, 2.1 * inch, 1.0 * inch, 1.0 * inch),
            repeatRows=1,
        )
        tableau.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), VERT),
                    ("GRID", (0, 0), (-1, -1), 0.35, LIGNE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f2f4f0")],
                    ),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(tableau)

    code_etudiant = getattr(acte.etudiant, "profil_etudiant", None)
    code_etudiant = getattr(code_etudiant, "code_etudiant", None) or "Non attribue"
    donnees = [
        ["Etudiant", acte.etudiant.get_full_name() or acte.etudiant.username],
        ["Code etudiant", code_etudiant],
        ["Programme", acte.programme.nom],
        ["Periode", f"{acte.periode.nom} - {acte.periode.annee_academique}"],
        ["Delivre le", acte.date_delivrance.strftime("%d/%m/%Y")],
    ]
    metadonnees = Table(
        [
            [_paragraph(cle, cell_style), _paragraph(valeur, cell_style)]
            for cle, valeur in donnees
        ],
        colWidths=(1.5 * inch, 5.0 * inch),
    )
    metadonnees.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, LIGNE),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            Spacer(1, 0.2 * inch),
            metadonnees,
            Spacer(1, 0.35 * inch),
            Table(
                [
                    [
                        _paragraph(
                            "Fait le " + acte.date_delivrance.strftime("%d/%m/%Y"),
                            cell_style,
                        ),
                        _paragraph("Pour le Registrariat", cell_style),
                    ],
                    ["", signature_pdf()],
                    [
                        "",
                        _paragraph(
                            acte.delivre_par.get_full_name()
                            or acte.delivre_par.username,
                            cell_style,
                        ),
                    ],
                    ["", _paragraph("Signature et sceau", cell_style)],
                ],
                colWidths=(3.25 * inch, 3.25 * inch),
                style=TableStyle(
                    [
                        ("ALIGN", (1, 0), (1, -1), "CENTER"),
                        ("LINEABOVE", (1, 2), (1, 2), 0.7, GRIS),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                ),
            ),
        ]
    )

    document.build(story, onFirstPage=pied_de_page, onLaterPages=pied_de_page)
    return tampon.getvalue()


def generer_pdf_proces_verbal(soutenance: SoutenanceMemoire):
    tampon = BytesIO()
    reference = f"PV-{soutenance.pk}"
    pied_de_page, configuration = entete_pied_pdf("Proces-verbal", reference)
    document = SimpleDocTemplate(
        tampon,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1.2 * inch,
        bottomMargin=0.8 * inch,
        title=f"Proces-verbal de soutenance - {soutenance.titre}",
        author=configuration.nom_site,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ProcesVerbalTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=22,
        alignment=TA_CENTER,
        textColor=VERT,
        spaceBefore=26,
        spaceAfter=22,
    )
    body_style = ParagraphStyle(
        "ProcesVerbalBody",
        parent=styles["BodyText"],
        fontSize=11,
        leading=18,
        spaceAfter=14,
    )
    cell_style = ParagraphStyle(
        "ProcesVerbalCell",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
    )
    nom = soutenance.etudiant.get_full_name() or soutenance.etudiant.username
    paragraphe = (
        f"Le jury a entendu <b>{escape(nom)}</b> presenter le memoire "
        f"<b>{escape(soutenance.titre)}</b> dans le cadre du programme "
        f"<b>{escape(soutenance.programme.nom)}</b>. La soutenance a eu lieu le "
        f"<b>{soutenance.date_soutenance.strftime('%d/%m/%Y')}</b>. "
        f"La note attribuee est de <b>{soutenance.note}/100</b>."
    )
    code_etudiant = getattr(soutenance.etudiant, "profil_etudiant", None)
    code_etudiant = getattr(code_etudiant, "code_etudiant", None) or "Non attribue"
    cellules = [
        ["Etudiant", nom],
        ["Code etudiant", code_etudiant],
        ["Programme", soutenance.programme.nom],
        [
            "Periode",
            f"{soutenance.periode.nom} - {soutenance.periode.annee_academique}",
        ],
        ["Memoire", soutenance.titre],
        ["Date", soutenance.date_soutenance.strftime("%d/%m/%Y")],
        ["Note", f"{soutenance.note}/100"],
        ["Jury", soutenance.jury or "Non renseigne"],
    ]
    details = Table(
        [
            [_paragraph(libelle, cell_style), _paragraph(valeur, cell_style)]
            for libelle, valeur in cellules
        ],
        colWidths=(1.5 * inch, 5.0 * inch),
    )
    details.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, LIGNE),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story = [
        _paragraph(soutenance.programme.entite.nom, styles["Normal"]),
        Spacer(1, 0.2 * inch),
        _paragraph("PROCES-VERBAL DE SOUTENANCE", title_style),
        Paragraph(paragraphe, body_style),
        Spacer(1, 0.15 * inch),
        details,
        Spacer(1, 0.4 * inch),
        Table(
            [
                ["", _paragraph("Pour le Registrariat", cell_style)],
                ["", signature_pdf()],
                [
                    "",
                    _paragraph(
                        soutenance.enregistre_par.get_full_name()
                        or soutenance.enregistre_par.username,
                        cell_style,
                    ),
                ],
                ["", _paragraph("Signature et sceau", cell_style)],
            ],
            colWidths=(3.25 * inch, 3.25 * inch),
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
