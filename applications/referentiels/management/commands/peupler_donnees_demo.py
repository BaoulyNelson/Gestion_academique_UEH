from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.inscriptions.models import (
    InscriptionPedagogique,
    PaiementScolarite,
    SelectionCours,
    TarifScolarite,
)
from applications.notes.models import Evaluation, ProgrammationExamen
from applications.rapports.models import (
    ActeAcademique,
    DossierEtudes,
    SoutenanceMemoire,
)
from applications.referentiels.models import (
    AffectationCours,
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
    RegleAcademique,
)


class Command(BaseCommand):
    help = "Cree un jeu de demonstration GP7 isole des donnees existantes."

    @transaction.atomic
    def handle(self, *args, **options):
        entite, _ = Entite.objects.get_or_create(
            code="demo-gp7-cdc",
            defaults={
                "nom": "DEMO GP7 - Seuils du cahier des charges",
                "regime": Entite.Regime.COHORTE,
            },
        )
        programme, _ = Programme.objects.get_or_create(
            entite=entite,
            code="demo-agronomie",
            defaults={
                "nom": "Programme de demonstration",
                "type_programme": Programme.TypeProgramme.FORMATION,
                "duree_annees": Decimal("3.0"),
            },
        )
        periode, _ = PeriodeAcademique.objects.get_or_create(
            entite=entite,
            code="demo-2026-2027",
            defaults={
                "nom": "Annee de demonstration",
                "annee_academique": "2026-2027",
                "type_periode": PeriodeAcademique.TypePeriode.ANNEE,
                "date_debut": date(2026, 9, 1),
                "date_fin": date(2027, 6, 30),
                "est_ouverte": True,
            },
        )
        RegleAcademique.objects.update_or_create(
            entite=entite,
            version="CDC-65-60",
            defaults={
                "date_effet": periode.date_debut,
                "parametres": {
                    "seuil_reussite_cours": "65",
                    "seuil_reprise_cours": "60",
                },
                "est_active": True,
            },
        )

        cours = []
        for code, nom, obligatoire in (
            ("DEMO101", "Cours obligatoire 1", True),
            ("DEMO102", "Cours obligatoire 2", True),
            ("DEMO103", "Cours optionnel", False),
        ):
            objet, _ = Cours.objects.get_or_create(
                programme=programme,
                code=code,
                defaults={
                    "nom": nom,
                    "credits": Decimal("3.00"),
                    "est_obligatoire": obligatoire,
                },
            )
            cours.append(objet)

        personnel = self._utilisateur(
            "demo-registrariat",
            "registrariat@example.test",
            entite,
            Utilisateur.Role.PERSONNEL,
            "Registrariat",
            "Demo",
        )
        professeur = self._utilisateur(
            "demo-professeur",
            "professeur@example.test",
            entite,
            Utilisateur.Role.PROFESSEUR,
            "Professeur",
            "Demo",
        )
        for objet in cours:
            AffectationCours.objects.get_or_create(
                professeur=professeur, cours=objet, periode=periode
            )

        for index, libelle, debut, fin, salle, statut in (
            (
                0,
                "Examen final - cours obligatoire 1",
                datetime(2026, 10, 20, 9, 0),
                datetime(2026, 10, 20, 11, 0),
                "Salle Demo 1",
                ProgrammationExamen.Statut.PLANIFIE,
            ),
            (
                1,
                "Examen partiel - cours obligatoire 2",
                datetime(2026, 10, 22, 13, 0),
                datetime(2026, 10, 22, 15, 0),
                "Salle Demo 2",
                ProgrammationExamen.Statut.PLANIFIE,
            ),
            (
                2,
                "Examen final - cours optionnel",
                datetime(2026, 10, 27, 9, 0),
                datetime(2026, 10, 27, 11, 0),
                "Salle Demo 1",
                ProgrammationExamen.Statut.PLANIFIE,
            ),
            (
                0,
                "Examen blanc (annule)",
                datetime(2026, 10, 29, 9, 0),
                datetime(2026, 10, 29, 10, 0),
                "Salle Demo 1",
                ProgrammationExamen.Statut.ANNULE,
            ),
        ):
            examen, _ = ProgrammationExamen.objects.update_or_create(
                cours=cours[index],
                periode=periode,
                libelle=libelle,
                defaults={
                    "date_debut": timezone.make_aware(debut),
                    "date_fin": timezone.make_aware(fin),
                    "salle": salle,
                    "consignes": "Examen de demonstration; se presenter 15 minutes avant.",
                    "statut": statut,
                    "planifie_par": personnel,
                },
            )
            examen.full_clean()
            examen.save()

        tarif, _ = TarifScolarite.objects.get_or_create(
            programme=programme,
            periode=periode,
            defaults={"montant": Decimal("25000.00"), "devise": "HTG"},
        )
        scenarios = (
            ("admis-65", "Etudiant", "Admis", "65.00", ProfilEtudiant.Sexe.FEMININ),
            (
                "reprise-60",
                "Etudiante",
                "Reprise",
                "60.00",
                ProfilEtudiant.Sexe.MASCULIN,
            ),
            ("echec-59", "Etudiant", "Echec", "59.00", ProfilEtudiant.Sexe.FEMININ),
            (
                "diplome-85",
                "Etudiante",
                "Diplome",
                "85.00",
                ProfilEtudiant.Sexe.MASCULIN,
            ),
        )
        maintenant = timezone.now()
        for suffixe, prenom, nom, note, sexe in scenarios:
            etudiant = self._utilisateur(
                f"demo-{suffixe}",
                f"{suffixe}@example.test",
                entite,
                Utilisateur.Role.ETUDIANT,
                prenom,
                nom,
            )
            ProfilEtudiant.objects.update_or_create(
                utilisateur=etudiant,
                defaults={
                    "code_etudiant": f"DEMO-GP7-{suffixe.upper()}",
                    "sexe": sexe,
                },
            )
            PaiementScolarite.objects.update_or_create(
                tarif=tarif,
                reference=f"DEMO-{suffixe.upper()}",
                defaults={
                    "etudiant": etudiant,
                    "montant": tarif.montant,
                    "date_paiement": date(2026, 9, 2),
                    "statut": PaiementScolarite.Statut.VALIDE,
                    "valide_par": personnel,
                    "date_validation": maintenant,
                },
            )
            inscription, _ = InscriptionPedagogique.objects.update_or_create(
                etudiant=etudiant,
                programme=programme,
                periode=periode,
                defaults={
                    "statut": InscriptionPedagogique.Statut.VALIDEE,
                    "conditions_passage_verifiees": True,
                    "traite_par": personnel,
                    "date_validation": maintenant,
                },
            )
            for objet in cours:
                SelectionCours.objects.get_or_create(
                    inscription=inscription, cours=objet
                )
                Evaluation.objects.update_or_create(
                    etudiant=etudiant,
                    cours=objet,
                    periode=periode,
                    libelle="Evaluation finale",
                    defaults={
                        "note": Decimal(note),
                        "coefficient": Decimal("1.00"),
                        "est_publiee": True,
                        "saisie_par": professeur,
                    },
                )

            statut_dossier = (
                DossierEtudes.Statut.DIPLOME
                if suffixe == "diplome-85"
                else DossierEtudes.Statut.EN_COURS
            )
            cloture = (
                date(2026, 9, 30)
                if statut_dossier == DossierEtudes.Statut.DIPLOME
                else None
            )
            DossierEtudes.objects.update_or_create(
                etudiant=etudiant,
                programme=programme,
                defaults={
                    "statut": statut_dossier,
                    "date_ouverture": date(2026, 9, 1),
                    "date_cloture": cloture,
                    "motif_cloture": (
                        "Fin du programme de demonstration" if cloture else ""
                    ),
                    "cree_par": personnel,
                },
            )
            for type_acte, code_acte in (
                (ActeAcademique.TypeActe.ATTESTATION_INSCRIPTION, "INS"),
                (ActeAcademique.TypeActe.RELEVE_NOTES, "REL"),
            ):
                ActeAcademique.objects.update_or_create(
                    reference=f"DEMO-{code_acte}-{suffixe.upper()}",
                    defaults={
                        "etudiant": etudiant,
                        "programme": programme,
                        "periode": periode,
                        "type_acte": type_acte,
                        "date_delivrance": date(2026, 10, 1),
                        "delivre_par": personnel,
                    },
                )

        diplome = Utilisateur.objects.get(username="demo-diplome-85")
        ActeAcademique.objects.update_or_create(
            reference="DEMO-DIP-DEMO-DIPLOME-85",
            defaults={
                "etudiant": diplome,
                "programme": programme,
                "periode": periode,
                "type_acte": ActeAcademique.TypeActe.DIPLOME,
                "date_delivrance": date(2026, 10, 1),
                "delivre_par": personnel,
            },
        )
        for suffixe, statut, note in (
            ("admis-65", SoutenanceMemoire.Statut.PLANIFIEE, None),
            ("diplome-85", SoutenanceMemoire.Statut.SOUTENUE, Decimal("85.00")),
        ):
            etudiant = Utilisateur.objects.get(username=f"demo-{suffixe}")
            SoutenanceMemoire.objects.update_or_create(
                etudiant=etudiant,
                programme=programme,
                titre=f"Memoire de demonstration {suffixe}",
                defaults={
                    "periode": periode,
                    "date_soutenance": date(2026, 10, 15),
                    "statut": statut,
                    "note": note,
                    "jury": "Jury de demonstration",
                    "enregistre_par": personnel,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Jeu de demonstration pret: 4 etudiants (moyennes 65, 60, 59 et 85), "
                "paiements, inscriptions, cours, notes publiees, examens, dossiers, "
                "actes et soutenances."
            )
        )

    @staticmethod
    def _utilisateur(username, email, entite, role, prenom, nom):
        utilisateur, cree = Utilisateur.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "entite": entite,
                "role": role,
                "first_name": prenom,
                "last_name": nom,
            },
        )
        if cree:
            utilisateur.set_unusable_password()
            utilisateur.save(update_fields=("password",))
        return utilisateur
