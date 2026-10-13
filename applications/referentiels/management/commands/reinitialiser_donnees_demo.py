import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.utils import timezone

from applications.comptes.models import ProfilEtudiant, SiteConfiguration, Utilisateur
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

ENTITES_DEMO = (
    {
        "code": "famv",
        "nom": "Faculte d'Agronomie et de Medecine Veterinaire",
        "regime": Entite.Regime.COHORTE,
        "type_periode": PeriodeAcademique.TypePeriode.QUADRIMESTRE,
        "seuil_reussite": 65,
        "seuil_reprise": 60,
        "note_echec": 52,
        "tarif": Decimal("25000.00"),
        "programmes": (
            (
                "agronomie",
                "Sciences agronomiques",
                Programme.TypeProgramme.SPECIALITE,
                None,
            ),
            (
                "veterinaire",
                "Medecine veterinaire",
                Programme.TypeProgramme.SPECIALITE,
                None,
            ),
        ),
        "cours": (
            ("Fondements de l'agronomie", Decimal("3"), True),
            ("Botanique appliquee", Decimal("3"), True),
            ("Gestion des sols", Decimal("3"), True),
            ("Economie rurale", Decimal("2"), False),
        ),
    },
    {
        "code": "fla",
        "nom": "Faculte de Linguistique Appliquee",
        "regime": Entite.Regime.COHORTE,
        "type_periode": PeriodeAcademique.TypePeriode.SESSION,
        "seuil_reussite": 60,
        "seuil_reprise": 40,
        "note_echec": 35,
        "tarif": Decimal("18000.00"),
        "programmes": (
            (
                "linguistique",
                "Linguistique appliquee",
                Programme.TypeProgramme.SPECIALITE,
                None,
            ),
            (
                "propedeutique",
                "Annee propedeutique",
                Programme.TypeProgramme.PROPEDEUTIQUE,
                None,
            ),
        ),
        "cours": (
            ("Linguistique generale", Decimal("3"), True),
            ("Grammaire du francais", Decimal("3"), True),
            ("Phonologie", Decimal("3"), True),
            ("Traduction", Decimal("2"), False),
        ),
    },
    {
        "code": "ierah-issers",
        "nom": "IERAH/ISSERS",
        "regime": Entite.Regime.CREDITS,
        "type_periode": PeriodeAcademique.TypePeriode.SESSION,
        "seuil_reussite": 60,
        "seuil_reprise": 55,
        "note_echec": 48,
        "tarif": Decimal("22000.00"),
        "programmes": (
            (
                "etudes-africaines",
                "Etudes africaines",
                Programme.TypeProgramme.FORMATION,
                None,
            ),
            (
                "sciences-sociales",
                "Sciences sociales",
                Programme.TypeProgramme.SPECIALITE,
                None,
            ),
        ),
        "cours": (
            ("Histoire contemporaine", Decimal("3"), True),
            ("Methodologie de recherche", Decimal("3"), True),
            ("Societes caribeennes", Decimal("3"), True),
            ("Developpement territorial", Decimal("2"), False),
        ),
    },
    {
        "code": "fasch",
        "nom": "Faculte des Sciences Humaines",
        "regime": Entite.Regime.CREDITS,
        "type_periode": PeriodeAcademique.TypePeriode.SESSION,
        "seuil_reussite": 60,
        "seuil_reprise": 55,
        "note_echec": 45,
        "tarif": Decimal("16000.00"),
        "programmes": (
            ("sociologie", "Sociologie", Programme.TypeProgramme.SPECIALITE, None),
            (
                "propedeutique",
                "Annee preparatoire",
                Programme.TypeProgramme.PROPEDEUTIQUE,
                30,
            ),
        ),
        "cours": (
            ("Introduction a la sociologie", Decimal("3"), True),
            ("Psychologie sociale", Decimal("3"), True),
            ("Methodologie", Decimal("3"), True),
            ("Socio-economie", Decimal("2"), False),
        ),
    },
)

SCENARIOS_ETUDIANTS = (
    ("admis", "Mireille", "Jean-Baptiste"),
    ("reprise", "Samuel", "Pierre-Louis"),
    ("echec", "Nadia", "Toussaint"),
    ("note-eliminatoire", "Kensley", "Charles"),
    ("notes-attente", "Roseline", "Bernard"),
    ("inscription-attente", "Patrick", "Louis"),
    ("paye-sans-inscription", "Nadine", "Baptiste"),
    ("paiement-partiel", "David", "Saint-Fleur"),
    ("sans-paiement", "Emeline", "Dorcely"),
    ("dossier-ferme", "Joel", "Alexis"),
    ("abandon", "Carline", "Pierre"),
    ("diplome", "Rebecca", "Jean"),
)


class Command(BaseCommand):
    help = (
        "Reinitialise les donnees de la base locale, conserve les superutilisateurs "
        "et cree un jeu de test pour les quatre entites du CDC."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Construit le jeu de donnees dans une transaction ensuite annulee.",
        )
        parser.add_argument(
            "--confirmer-reinitialisation",
            action="store_true",
            help="Confirme la suppression de toutes les donnees hors superutilisateurs.",
        )

    def handle(self, *args, **options):
        self.mot_de_passe_demo = secrets.token_urlsafe(18)
        self.comptes_demo = {role: [] for role in Utilisateur.Role.values}
        if options["dry_run"]:
            with transaction.atomic():
                self._creer_jeu_de_test()
                transaction.set_rollback(True)
            self.stdout.write(
                self.style.SUCCESS(
                    "Simulation reussie; aucune donnee n'a ete conservee."
                )
            )
            return
        if not options["confirmer_reinitialisation"]:
            raise CommandError(
                "Cette commande efface toutes les donnees applicatives. "
                "Relancez-la avec --confirmer-reinitialisation apres sauvegarde."
            )

        superutilisateurs = list(
            Utilisateur.objects.filter(is_superuser=True).values(
                "id",
                "username",
                "password",
                "email",
                "first_name",
                "last_name",
                "is_staff",
                "is_active",
                "date_joined",
                "last_login",
            )
        )
        if not superutilisateurs:
            raise CommandError(
                "Aucun superutilisateur a conserver. Creez-en un avant la reinitialisation."
            )

        call_command("flush", interactive=False, verbosity=0)
        for donnees in superutilisateurs:
            Utilisateur.objects.create(
                **donnees,
                role=Utilisateur.Role.ADMINISTRATEUR,
                is_superuser=True,
                entite=None,
            )

        with transaction.atomic():
            self._creer_jeu_de_test()

        self.stdout.write(self.style.SUCCESS("Base de test GP7 reconstruite."))
        self.stdout.write(f"Superutilisateur conserve(s): {len(superutilisateurs)}.")
        self.stdout.write("Entites: FAMV, FLA, IERAH/ISSERS, FASCH.")
        self.stdout.write(
            "Mot de passe commun des comptes demo: " f"{self.mot_de_passe_demo}"
        )
        self.stdout.write(
            "Comptes: demo_gp7_registrariat_<entite>, "
            "demo_gp7_prof_<entite>_<programme>, "
            "demo_gp7_etudiant_<entite>_<programme>_<scenario>."
        )

    def _creer_jeu_de_test(self):
        SiteConfiguration.objects.update_or_create(
            pk=1,
            defaults={
                "nom_site": "GP7 | UEH",
                "slogan": "Environnement de demonstration academique",
                "telephone": "+509 0000-0000",
                "email_contact": "registrariat@demo.ueh.test",
                "adresse": "Port-au-Prince, Haiti",
                "texte_pied_page": "Donnees fictives pour tests locaux uniquement.",
            },
        )
        maintenant = timezone.now()
        for index_entite, spec in enumerate(ENTITES_DEMO):
            entite, _ = Entite.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "nom": spec["nom"],
                    "regime": spec["regime"],
                    "est_active": True,
                },
            )
            periode_precedente, periode_actuelle = self._creer_periodes(entite, spec)
            RegleAcademique.objects.update_or_create(
                entite=entite,
                version=f"DEMO-CDC-{entite.code.upper()}-2026",
                defaults={
                    "date_effet": periode_actuelle.date_debut,
                    "est_active": True,
                    "parametres": {
                        "seuil_reussite_cours": str(spec["seuil_reussite"]),
                        "seuil_reprise_cours": str(spec["seuil_reprise"]),
                        "note_eliminatoire": "35",
                        "mentions": {
                            "Passable": 60,
                            "Bien": 70,
                            "Tres bien": 85,
                        },
                    },
                },
            )
            registrariat = self._creer_utilisateur(
                f"demo_gp7_registrariat_{entite.code}",
                entite,
                Utilisateur.Role.PERSONNEL,
                "Registrariat",
                entite.code.upper(),
            )

            niveau_demo = None
            if entite.code == "fasch":
                niveau_demo, _ = PeriodeAcademique.objects.update_or_create(
                    entite=entite,
                    code="demo-niveau-1-2026",
                    defaults={
                        "nom": "Niveau 1 - demonstration",
                        "annee_academique": "2026-2027",
                        "type_periode": PeriodeAcademique.TypePeriode.NIVEAU,
                        "date_debut": date(2026, 10, 1),
                        "date_fin": date(2027, 6, 30),
                        "est_ouverte": True,
                    },
                )

            for index_programme, programme_spec in enumerate(spec["programmes"]):
                self._creer_programme(
                    entite,
                    spec,
                    programme_spec,
                    registrariat,
                    periode_precedente,
                    periode_actuelle,
                    index_entite,
                    index_programme,
                    maintenant,
                    niveau_demo if index_programme == 1 else None,
                )

    def _creer_periodes(self, entite, spec):
        if spec["type_periode"] == PeriodeAcademique.TypePeriode.QUADRIMESTRE:
            definitions = (
                (
                    "demo-2025-2026",
                    "Quadrimestre 2025-2026",
                    "2025-2026",
                    date(2025, 10, 1),
                    date(2026, 6, 30),
                    False,
                ),
                (
                    "demo-2026-2027",
                    "Quadrimestre 2026-2027",
                    "2026-2027",
                    date(2026, 10, 1),
                    date(2027, 6, 30),
                    True,
                ),
            )
        else:
            definitions = (
                (
                    "demo-session-printemps-2026",
                    "Session de printemps 2026",
                    "2025-2026",
                    date(2026, 1, 15),
                    date(2026, 6, 30),
                    False,
                ),
                (
                    "demo-session-automne-2026",
                    "Session d'automne 2026",
                    "2026-2027",
                    date(2026, 10, 1),
                    date(2027, 2, 15),
                    True,
                ),
            )
        periodes = []
        for code, nom, annee, debut, fin, ouverte in definitions:
            periode, _ = PeriodeAcademique.objects.update_or_create(
                entite=entite,
                code=code,
                defaults={
                    "nom": nom,
                    "annee_academique": annee,
                    "type_periode": spec["type_periode"],
                    "date_debut": debut,
                    "date_fin": fin,
                    "est_ouverte": ouverte,
                },
            )
            periodes.append(periode)
        return periodes

    def _creer_programme(
        self,
        entite,
        entite_spec,
        programme_spec,
        registrariat,
        periode_precedente,
        periode_actuelle,
        index_entite,
        index_programme,
        maintenant,
        niveau_demo,
    ):
        code, nom, type_programme, credits_requis = programme_spec
        programme, _ = Programme.objects.update_or_create(
            entite=entite,
            code=code,
            defaults={
                "nom": nom,
                "type_programme": type_programme,
                "duree_annees": Decimal("3.0"),
                "credits_requis": credits_requis,
                "est_actif": True,
            },
        )
        cours_spec = entite_spec["cours"]
        if credits_requis:
            cours_spec = (
                (cours_spec[0][0], Decimal("8"), True),
                (cours_spec[1][0], Decimal("8"), True),
                (cours_spec[2][0], Decimal("7"), True),
                (cours_spec[3][0], Decimal("7"), False),
            )
        cours = []
        prefixe = "".join(part[0] for part in code.split("-")).upper()[:5]
        for index, (nom_cours, credits, obligatoire) in enumerate(cours_spec, start=1):
            objet, _ = Cours.objects.update_or_create(
                programme=programme,
                code=f"{prefixe}{index:02d}",
                defaults={
                    "nom": nom_cours,
                    "credits": credits,
                    "est_obligatoire": obligatoire,
                    "est_actif": True,
                },
            )
            cours.append(objet)

        professeur = self._creer_utilisateur(
            f"demo_gp7_prof_{entite.code}_{code}",
            entite,
            Utilisateur.Role.PROFESSEUR,
            "Professeur",
            nom,
        )
        for periode in (periode_precedente, periode_actuelle):
            for objet in cours:
                AffectationCours.objects.get_or_create(
                    professeur=professeur,
                    cours=objet,
                    periode=periode,
                )
        self._creer_examens(
            cours,
            periode_actuelle,
            registrariat,
            index_entite,
            index_programme,
        )

        tarifs = {}
        for periode in (periode_precedente, periode_actuelle):
            tarif, _ = TarifScolarite.objects.update_or_create(
                programme=programme,
                periode=periode,
                defaults={
                    "montant": entite_spec["tarif"],
                    "devise": "HTG",
                    "est_actif": True,
                },
            )
            tarifs[periode.pk] = tarif

        for index_etudiant, scenario in enumerate(SCENARIOS_ETUDIANTS, start=1):
            slug, prenom, nom_etudiant = scenario
            etudiant = self._creer_utilisateur(
                f"demo_gp7_etudiant_{entite.code}_{code}_{slug}",
                entite,
                Utilisateur.Role.ETUDIANT,
                prenom,
                nom_etudiant,
            )
            code_etudiant = (
                f"{entite.code.upper()[:4]}-{code.upper()[:6]}-26-{index_etudiant:03d}"
            )
            ProfilEtudiant.objects.update_or_create(
                utilisateur=etudiant,
                defaults={
                    "code_etudiant": code_etudiant,
                    "nif": f"NIF-{entite.code.upper()[:4]}-{code.upper()[:4]}-{index_etudiant:03d}",
                    "cin": f"CIN-{entite.code.upper()[:4]}-{code.upper()[:4]}-{index_etudiant:03d}",
                    "sexe": (
                        ProfilEtudiant.Sexe.FEMININ
                        if index_etudiant % 2
                        else ProfilEtudiant.Sexe.MASCULIN
                    ),
                    "date_naissance": date(
                        2002 + index_etudiant % 5, 3 + index_etudiant % 8, 12
                    ),
                    "telephone": f"+509 37{index_entite}{index_programme}{index_etudiant:02d} 0000",
                    "adresse": "Port-au-Prince, Haiti",
                },
            )

            tarif_precedent = tarifs[periode_precedente.pk]
            tarif_actuel = tarifs[periode_actuelle.pk]
            self._creer_paiement(
                etudiant,
                tarif_precedent,
                f"DEMO-PREV-{entite.code}-{code}-{slug}",
                tarif_precedent.montant,
                PaiementScolarite.Statut.VALIDE,
                registrariat,
            )
            inscription_precedente = self._creer_inscription(
                etudiant,
                programme,
                periode_precedente,
                registrariat,
                InscriptionPedagogique.Statut.VALIDEE,
            )
            self._creer_selections(inscription_precedente, cours)
            self._creer_evaluations(
                etudiant,
                cours,
                periode_precedente,
                professeur,
                Decimal("78"),
                True,
            )

            inscription_actuelle = self._creer_scenario_actuel(
                slug,
                etudiant,
                programme,
                periode_actuelle,
                tarif_actuel,
                registrariat,
                professeur,
                cours,
                entite_spec,
            )
            if niveau_demo and slug == "admis":
                inscription_niveau = self._creer_inscription(
                    etudiant,
                    programme,
                    niveau_demo,
                    registrariat,
                    InscriptionPedagogique.Statut.VALIDEE,
                )
                self._creer_selections(inscription_niveau, cours)
            statut_dossier = self._statut_dossier(slug)
            dossier = self._creer_dossier(
                etudiant,
                programme,
                registrariat,
                statut_dossier,
                periode_precedente.date_debut,
                periode_precedente.date_fin,
            )
            self._creer_actes(
                etudiant,
                programme,
                periode_precedente,
                periode_actuelle,
                registrariat,
                inscription_precedente,
                inscription_actuelle,
                slug,
                dossier,
            )
            if slug == "admis":
                self._creer_soutenance(
                    etudiant,
                    programme,
                    periode_actuelle,
                    registrariat,
                    SoutenanceMemoire.Statut.PLANIFIEE,
                    None,
                    f"Projet de fin d'etudes {code_etudiant}",
                )
            if slug == "diplome":
                self._creer_soutenance(
                    etudiant,
                    programme,
                    periode_precedente,
                    registrariat,
                    SoutenanceMemoire.Statut.SOUTENUE,
                    Decimal("86.00"),
                    f"Memoire soutenu {code_etudiant}",
                )

    def _creer_scenario_actuel(
        self,
        slug,
        etudiant,
        programme,
        periode,
        tarif,
        registrariat,
        professeur,
        cours,
        entite_spec,
    ):
        montant = tarif.montant
        if slug in {
            "admis",
            "reprise",
            "echec",
            "note-eliminatoire",
            "notes-attente",
            "inscription-attente",
            "paye-sans-inscription",
        }:
            self._creer_paiement(
                etudiant,
                tarif,
                f"DEMO-CURRENT-{etudiant.username}",
                montant,
                PaiementScolarite.Statut.VALIDE,
                registrariat,
            )
        elif slug == "paiement-partiel":
            self._creer_paiement(
                etudiant,
                tarif,
                f"DEMO-PARTIAL-VALID-{etudiant.username}",
                montant * Decimal("0.40"),
                PaiementScolarite.Statut.VALIDE,
                registrariat,
            )
            self._creer_paiement(
                etudiant,
                tarif,
                f"DEMO-PARTIAL-PENDING-{etudiant.username}",
                montant * Decimal("0.20"),
                PaiementScolarite.Statut.EN_ATTENTE,
                None,
            )

        if slug in {"admis", "reprise", "echec", "note-eliminatoire", "notes-attente"}:
            inscription = self._creer_inscription(
                etudiant,
                programme,
                periode,
                registrariat,
                InscriptionPedagogique.Statut.VALIDEE,
            )
            self._creer_selections(inscription, cours)
            note = {
                "admis": Decimal("82"),
                "reprise": (
                    Decimal(str(entite_spec["seuil_reussite"]))
                    + Decimal(str(entite_spec["seuil_reprise"]))
                )
                / Decimal("2"),
                "echec": entite_spec["note_echec"],
                "note-eliminatoire": Decimal("75"),
                "notes-attente": Decimal("70"),
            }[slug]
            self._creer_evaluations(
                etudiant,
                cours,
                periode,
                professeur,
                note,
                slug != "notes-attente",
                slug == "note-eliminatoire",
            )
            return inscription
        if slug == "inscription-attente":
            return self._creer_inscription(
                etudiant,
                programme,
                periode,
                registrariat,
                InscriptionPedagogique.Statut.EN_ATTENTE,
            )
        return None

    def _creer_inscription(self, etudiant, programme, periode, registrariat, statut):
        inscription, _ = InscriptionPedagogique.objects.update_or_create(
            etudiant=etudiant,
            programme=programme,
            periode=periode,
            defaults={
                "statut": statut,
                "conditions_passage_verifiees": (
                    statut == InscriptionPedagogique.Statut.VALIDEE
                ),
                "traite_par": (
                    registrariat
                    if statut
                    in {
                        InscriptionPedagogique.Statut.VALIDEE,
                        InscriptionPedagogique.Statut.REFUSEE,
                    }
                    else None
                ),
                "date_validation": (
                    timezone.now()
                    if statut
                    in {
                        InscriptionPedagogique.Statut.VALIDEE,
                        InscriptionPedagogique.Statut.REFUSEE,
                    }
                    else None
                ),
            },
        )
        if statut == InscriptionPedagogique.Statut.VALIDEE:
            inscription.full_clean()
        inscription.save()
        return inscription

    def _creer_selections(self, inscription, cours):
        for objet in cours:
            SelectionCours.objects.get_or_create(inscription=inscription, cours=objet)

    def _creer_evaluations(
        self, etudiant, cours, periode, professeur, note, publiee, eliminatoire=False
    ):
        for index, objet in enumerate(cours):
            evaluations = (
                ("Controle continu", Decimal("1.00"), Decimal("3")),
                ("Examen final", Decimal("2.00"), Decimal("-1")),
            )
            for libelle, coefficient, ajustement in evaluations:
                valeur = min(max(note + ajustement, Decimal("0")), Decimal("100"))
                if eliminatoire and index == 0 and libelle == "Examen final":
                    libelle = "Examen final - note eliminatoire"
                    valeur = Decimal("25")
                evaluation, _ = Evaluation.objects.update_or_create(
                    etudiant=etudiant,
                    cours=objet,
                    periode=periode,
                    libelle=libelle,
                    defaults={
                        "note": valeur,
                        "coefficient": coefficient,
                        "est_publiee": publiee,
                        "saisie_par": professeur,
                    },
                )
                if evaluation.est_publiee:
                    evaluation.full_clean()
                    evaluation.save()

    def _creer_paiement(self, etudiant, tarif, reference, montant, statut, valide_par):
        montant = Decimal(montant).quantize(Decimal("0.01"))
        paiement, _ = PaiementScolarite.objects.update_or_create(
            tarif=tarif,
            reference=reference,
            defaults={
                "etudiant": etudiant,
                "montant": montant,
                "date_paiement": date(2026, 10, 2),
                "statut": statut,
                "valide_par": valide_par,
                "date_validation": timezone.now() if valide_par else None,
                "motif_refus": "",
            },
        )
        paiement.full_clean()
        paiement.save()
        return paiement

    def _statut_dossier(self, scenario):
        return {
            "dossier-ferme": DossierEtudes.Statut.FERME,
            "abandon": DossierEtudes.Statut.ABANDON,
            "diplome": DossierEtudes.Statut.DIPLOME,
        }.get(scenario, DossierEtudes.Statut.EN_COURS)

    def _creer_dossier(
        self, etudiant, programme, registrariat, statut, ouverture, cloture
    ):
        date_cloture = cloture if statut != DossierEtudes.Statut.EN_COURS else None
        dossier, _ = DossierEtudes.objects.update_or_create(
            etudiant=etudiant,
            programme=programme,
            defaults={
                "statut": statut,
                "date_ouverture": ouverture,
                "date_cloture": date_cloture,
                "motif_cloture": (
                    "Fin de parcours de demonstration"
                    if statut == DossierEtudes.Statut.DIPLOME
                    else "Fermeture de demonstration" if date_cloture else ""
                ),
                "cree_par": registrariat,
            },
        )
        dossier.full_clean()
        dossier.save()
        return dossier

    def _creer_actes(
        self,
        etudiant,
        programme,
        periode_precedente,
        periode_actuelle,
        registrariat,
        inscription_precedente,
        inscription_actuelle,
        scenario,
        dossier,
    ):
        actes = [
            (
                periode_precedente,
                ActeAcademique.TypeActe.ATTESTATION_INSCRIPTION,
                f"DEMO-INS-{etudiant.username}",
            ),
            (
                periode_precedente,
                ActeAcademique.TypeActe.RELEVE_NOTES,
                f"DEMO-REL-{etudiant.username}",
            ),
        ]
        if inscription_actuelle and scenario in {
            "admis",
            "reprise",
            "echec",
            "note-eliminatoire",
        }:
            actes.extend(
                (
                    periode_actuelle,
                    type_acte,
                    f"CUR-{type_acte.value[:3].upper()}-{etudiant.pk}",
                )
                for type_acte in (
                    ActeAcademique.TypeActe.ATTESTATION_INSCRIPTION,
                    ActeAcademique.TypeActe.RELEVE_NOTES,
                )
            )
        if dossier.statut == DossierEtudes.Statut.DIPLOME:
            actes.append(
                (
                    periode_precedente,
                    ActeAcademique.TypeActe.DIPLOME,
                    f"DEMO-DIP-{etudiant.username}",
                )
            )
        for periode, type_acte, reference in actes:
            acte, _ = ActeAcademique.objects.update_or_create(
                reference=reference,
                defaults={
                    "etudiant": etudiant,
                    "programme": programme,
                    "periode": periode,
                    "type_acte": type_acte,
                    "date_delivrance": date(2026, 10, 10),
                    "delivre_par": registrariat,
                    "est_annule": False,
                },
            )
            acte.full_clean()
            acte.save()

    def _creer_soutenance(
        self, etudiant, programme, periode, registrariat, statut, note, titre
    ):
        soutenance, _ = SoutenanceMemoire.objects.update_or_create(
            etudiant=etudiant,
            programme=programme,
            titre=titre,
            defaults={
                "periode": periode,
                "date_soutenance": (
                    date(2026, 11, 20)
                    if statut == SoutenanceMemoire.Statut.PLANIFIEE
                    else date(2026, 6, 15)
                ),
                "statut": statut,
                "note": note,
                "jury": "Jury de demonstration",
                "enregistre_par": registrariat,
            },
        )
        return soutenance

    def _creer_examens(
        self, cours, periode, registrariat, index_entite, index_programme
    ):
        for index, objet in enumerate(cours):
            jour = 2 + index_programme * 5 + index
            debut = datetime.combine(date(2026, 11, jour), time(9 + index, 0))
            examen, _ = ProgrammationExamen.objects.update_or_create(
                cours=objet,
                periode=periode,
                libelle=f"Examen final - {objet.code}",
                defaults={
                    "date_debut": timezone.make_aware(debut),
                    "date_fin": timezone.make_aware(debut + timedelta(hours=2)),
                    "salle": f"Salle {index_entite + 1}-{index_programme + 1}-{index + 1}",
                    "consignes": "Examen fictif de demonstration.",
                    "statut": ProgrammationExamen.Statut.PLANIFIE,
                    "planifie_par": registrariat,
                },
            )
            examen.full_clean()
            examen.save()

    def _creer_utilisateur(self, username, entite, role, prenom, nom):
        email = f"{username}@demo.ueh.test"
        utilisateur, _ = Utilisateur.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "entite": entite,
                "role": role,
                "first_name": prenom,
                "last_name": nom,
            },
        )
        utilisateur.email = email
        utilisateur.entite = entite
        utilisateur.role = role
        utilisateur.first_name = prenom
        utilisateur.last_name = nom
        utilisateur.is_active = True
        utilisateur.set_password(self.mot_de_passe_demo)
        utilisateur.save()
        self.comptes_demo[role].append(username)
        return utilisateur
