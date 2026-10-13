from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image

from applications.comptes.models import SiteConfiguration


VERT = colors.HexColor("#1c493d")
GRIS = colors.HexColor("#53615b")
OR = colors.HexColor("#c99a35")
LIGNE = colors.HexColor("#d7ddd7")


def signature_pdf():
    chemin = Path(settings.PDF_SIGNATURE_PATH)
    if not chemin.is_file():
        raise FileNotFoundError(f"Signature PDF introuvable : {chemin}")
    return Image(
        str(chemin),
        width=1.65 * inch,
        height=0.48 * inch,
        kind="proportional",
    )


def entete_pied_pdf(libelle, reference):
    configuration = SiteConfiguration.get_solo()
    largeur_page, hauteur_page = letter

    def dessiner(canvas, document):
        canvas.saveState()
        logo = settings.BASE_DIR / "static" / "images" / "logo.png"
        if configuration.logo:
            logo_configure = Path(configuration.logo.path)
            if logo_configure.is_file():
                logo = logo_configure
        if logo.is_file():
            canvas.drawImage(
                ImageReader(str(logo)),
                0.65 * inch,
                hauteur_page - 0.91 * inch,
                width=0.62 * inch,
                height=0.62 * inch,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )

        x_texte = 1.38 * inch
        canvas.setFillColor(VERT)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(
            x_texte,
            hauteur_page - 0.46 * inch,
            configuration.nom_site[:72],
        )
        canvas.setFillColor(GRIS)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            x_texte,
            hauteur_page - 0.65 * inch,
            configuration.slogan[:100],
        )
        coordonnees = " | ".join(
            valeur
            for valeur in (
                configuration.adresse,
                configuration.email_contact,
                configuration.telephone,
            )
            if valeur
        )
        if coordonnees:
            canvas.setFont("Helvetica", 7)
            canvas.drawString(
                x_texte,
                hauteur_page - 0.82 * inch,
                coordonnees[:125],
            )

        canvas.setFillColor(GRIS)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(
            largeur_page - 0.65 * inch,
            hauteur_page - 0.47 * inch,
            libelle.upper()[:34],
        )
        canvas.setStrokeColor(OR)
        canvas.setLineWidth(1.5)
        canvas.line(
            0.65 * inch,
            hauteur_page - 1.02 * inch,
            largeur_page - 0.65 * inch,
            hauteur_page - 1.02 * inch,
        )

        canvas.setStrokeColor(LIGNE)
        canvas.setLineWidth(0.6)
        canvas.line(0.65 * inch, 0.64 * inch, largeur_page - 0.65 * inch, 0.64 * inch)
        canvas.setFillColor(GRIS)
        canvas.setFont("Helvetica", 7)
        pied = " | ".join(
            valeur
            for valeur in (
                configuration.adresse,
                configuration.email_contact,
                configuration.telephone,
            )
            if valeur
        )
        canvas.drawString(0.65 * inch, 0.47 * inch, pied[:115] or configuration.nom_site)
        canvas.drawString(
            0.65 * inch,
            0.31 * inch,
            f"GP7 | {libelle} | Reference {reference}"[:115],
        )
        canvas.drawRightString(
            largeur_page - 0.65 * inch,
            0.31 * inch,
            f"Page {document.page}",
        )
        canvas.restoreState()

    return dessiner, configuration
