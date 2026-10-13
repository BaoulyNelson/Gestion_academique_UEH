import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from applications.entites.models import Entite, Option


class Command(BaseCommand):
    help = "Importe les options de candidature à partir d’un fichier CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fichier",
            default=str(settings.BASE_DIR / "data" / "options.csv"),
            help="Chemin du CSV (colonnes requises : code_entite, nom).",
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
                manquantes = {"code_entite", "nom"} - colonnes
                if manquantes:
                    raise CommandError(
                        "Colonnes manquantes dans le CSV : "
                        + ", ".join(sorted(manquantes))
                    )

                options_creees = 0
                options_existantes = 0
                options_lues = set()
                for numero_ligne, ligne in enumerate(lecteur, start=2):
                    code = (ligne.get("code_entite") or "").strip()
                    nom = (ligne.get("nom") or "").strip()
                    if not code or not nom:
                        raise CommandError(
                            f"Le code d’entité et le nom sont obligatoires "
                            f"(ligne {numero_ligne})."
                        )
                    cle = (code, nom)
                    if cle in options_lues:
                        raise CommandError(
                            f"Option en double « {nom} » pour l’entité « {code} » "
                            f"(ligne {numero_ligne})."
                        )
                    options_lues.add(cle)
                    entite = Entite.objects.filter(code=code).first()
                    if entite is None:
                        raise CommandError(
                            f"Entité inconnue « {code} » (ligne {numero_ligne})."
                        )
                    _, creee = Option.objects.get_or_create(
                        entite=entite,
                        nom=nom,
                        defaults={"active": True},
                    )
                    if creee:
                        options_creees += 1
                    else:
                        options_existantes += 1
        except UnicodeDecodeError as erreur:
            raise CommandError("Le fichier CSV doit être encodé en UTF-8.") from erreur

        self.stdout.write(
            self.style.SUCCESS(
                f"Import terminé : {options_creees} option(s) créée(s), "
                f"{options_existantes} déjà présente(s)."
            )
        )
