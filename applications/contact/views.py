from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from applications.comptes.models import SiteConfiguration

from .forms import FormulaireContact


def contact(request):
    configuration = SiteConfiguration.get_solo()
    formulaire = FormulaireContact(request.POST or None)

    if request.method == "POST" and formulaire.is_valid():
        if not configuration.email_contact:
            messages.error(
                request,
                "Le formulaire de contact est indisponible pour le moment.",
            )
        else:
            donnees = formulaire.cleaned_data
            EmailMessage(
                subject=f"[{configuration.nom_site}] {donnees['sujet']}",
                body=(
                    f"Nom : {donnees['nom']}\n"
                    f"E-mail : {donnees['email']}\n\n"
                    f"{donnees['message']}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[configuration.email_contact],
                reply_to=[donnees["email"]],
            ).send()
            messages.success(
                request,
                "Votre message a ete envoye. Nous vous repondrons des que possible.",
            )
            return redirect(reverse("contact:contact"))

    return render(
        request,
        "public/contact.html",
        {
            "site_config": configuration,
            "formulaire": formulaire,
            "annee_courante": timezone.localdate().year,
        },
    )
