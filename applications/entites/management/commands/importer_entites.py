import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from applications.entites.models import Entite


class Command(BaseCommand):
    help = "Importe ou met à jour les entités à partir d’un fichier CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fichier",
            default=str(settings.BASE_DIR / "data" / "entites.csv"),
            help="Chemin du fichier CSV (colonnes requises : code, nom, email).",
        )

    @transaction.atomic
    def handle(self, *args, fichier, **options):
        chemin = Path(fichier)
        if not chemin.is_file():
            raise CommandError(f"Fichier CSV introuvable : {chemin}")

        try:
            with chemin.open("r", encoding="utf-8-sig", newline="") as source:
                lecteur = csv.DictReader(source)
                colonnes = set(lecteur.fieldnames or [])
                manquantes = {"code", "nom", "email"} - colonnes
                if manquantes:
                    raise CommandError(
                        "Colonnes manquantes dans le CSV : "
                        + ", ".join(sorted(manquantes))
                    )

                entites_creees = 0
                entites_mises_a_jour = 0
                codes_lus = set()
                for numero_ligne, ligne in enumerate(lecteur, start=2):
                    code = (ligne.get("code") or "").strip()
                    nom = (ligne.get("nom") or "").strip()
                    email = (ligne.get("email") or "").strip()
                    if not code or not nom:
                        raise CommandError(
                            f"Le code et le nom sont obligatoires (ligne {numero_ligne})."
                        )
                    if code in codes_lus:
                        raise CommandError(
                            f"Code d’entité en double « {code} » (ligne {numero_ligne})."
                        )
                    codes_lus.add(code)
                    _, creee = Entite.objects.update_or_create(
                        code=code,
                        defaults={"nom": nom, "email_contact": email},
                    )
                    if creee:
                        entites_creees += 1
                    else:
                        entites_mises_a_jour += 1
        except UnicodeDecodeError as erreur:
            raise CommandError("Le fichier CSV doit être encodé en UTF-8.") from erreur

        self.stdout.write(
            self.style.SUCCESS(
                f"Import terminé : {entites_creees} entité(s) créée(s), "
                f"{entites_mises_a_jour} mise(s) à jour."
            )
        )
