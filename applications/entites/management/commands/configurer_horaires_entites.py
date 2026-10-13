from django.core.management.base import BaseCommand
from django.db import transaction

from applications.entites.models import Entite, HoraireEntite


class Command(BaseCommand):
    help = "Active les vacations AM et PM pour toutes les entités."

    @transaction.atomic
    def handle(self, *args, **options):
        crees = 0
        reactives = 0
        for entite in Entite.objects.all().iterator():
            for code in HoraireEntite.Code.values:
                horaire, cree = HoraireEntite.objects.get_or_create(
                    entite=entite,
                    code=code,
                    defaults={"actif": True},
                )
                if cree:
                    crees += 1
                elif not horaire.actif:
                    horaire.actif = True
                    horaire.save(update_fields=["actif"])
                    reactives += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Configuration terminée : {crees} vacation(s) créée(s), "
                f"{reactives} réactivée(s)."
            )
        )
