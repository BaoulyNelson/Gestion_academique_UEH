from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage

from applications.candidatures.models import Inscription
from applications.candidatures.pdf import generer_pdf_inscription


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def envoyer_confirmation_inscription(self, inscription_id):
    inscription = Inscription.objects.select_related(
        "candidat__utilisateur", "entite"
    ).get(pk=inscription_id)
    candidat = inscription.candidat.utilisateur
    courriel = EmailMessage(
        subject=f"Confirmation de votre dossier #{inscription.numero_dossier}",
        body=(
            f"Bonjour {candidat.prenom or candidat.email},\n\n"
            f"Votre candidature auprès de {inscription.entite} a été reçue.\n"
            f"Votre numéro de dossier est #{inscription.numero_dossier}.\n"
            "Connectez-vous à votre espace pour suivre son traitement."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[candidat.email],
    )
    courriel.attach(
        f"dossier-{inscription.numero_dossier}.pdf",
        generer_pdf_inscription(inscription),
        "application/pdf",
    )
    return courriel.send(fail_silently=False)
