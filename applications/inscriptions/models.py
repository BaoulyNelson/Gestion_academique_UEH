from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class InscriptionPedagogique(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDEE = "validee", "Validee"
        REFUSEE = "refusee", "Refusee"
        ANNULEE = "annulee", "Annulee"

    etudiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="etudiant",
        on_delete=models.PROTECT,
        related_name="inscriptions_pedagogiques",
    )
    programme = models.ForeignKey(
        "referentiels.Programme",
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="inscriptions",
    )
    periode = models.ForeignKey(
        "referentiels.PeriodeAcademique",
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="inscriptions",
    )
    statut = models.CharField(
        "statut", max_length=16, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    conditions_passage_verifiees = models.BooleanField(
        "conditions de passage verifiees", default=False
    )
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="traite par",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inscriptions_traitees",
    )
    motif_decision = models.CharField(
        "motif de la decision", max_length=240, blank=True
    )
    date_creation = models.DateTimeField("date de creation", auto_now_add=True)
    date_validation = models.DateTimeField("date de validation", null=True, blank=True)

    class Meta:
        ordering = ("-date_creation",)
        constraints = [
            models.UniqueConstraint(
                fields=("etudiant", "programme", "periode"),
                name="uniq_inscription_etudiant_programme_periode",
            )
        ]
        verbose_name = "inscription pedagogique"
        verbose_name_plural = "inscriptions pedagogiques"

    def clean(self):
        if self.programme_id and self.periode_id:
            if self.programme.entite_id != self.periode.entite_id:
                raise ValidationError(
                    "Le programme et la periode doivent appartenir a la meme entite."
                )
        if self.etudiant_id and self.etudiant.role != self.etudiant.Role.ETUDIANT:
            raise ValidationError(
                {"etudiant": "Le compte selectionne n'a pas le role etudiant."}
            )
        if self.etudiant_id and self.programme_id:
            if self.etudiant.entite_id != self.programme.entite_id:
                raise ValidationError(
                    {
                        "programme": "Le programme doit appartenir a l'entite de l'etudiant."
                    }
                )
        if self.statut in {self.Statut.VALIDEE, self.Statut.REFUSEE}:
            if not self.traite_par_id:
                raise ValidationError(
                    {"traite_par": "Un membre du registrariat doit traiter la demande."}
                )
            if not self.traite_par.is_superuser:
                if self.traite_par.role != self.traite_par.Role.PERSONNEL:
                    raise ValidationError(
                        {"traite_par": "Seul le registrariat peut traiter la demande."}
                    )
                if self.traite_par.entite_id != self.programme.entite_id:
                    raise ValidationError(
                        {
                            "traite_par": "Le registrariat doit appartenir a la meme entite."
                        }
                    )
        if self.statut == self.Statut.VALIDEE and not self.conditions_passage_verifiees:
            raise ValidationError(
                {
                    "conditions_passage_verifiees": "Les conditions de passage doivent etre verifiees."
                }
            )
        if self.statut == self.Statut.REFUSEE and not self.motif_decision.strip():
            raise ValidationError(
                {"motif_decision": "Le motif du refus est obligatoire."}
            )

    def __str__(self):
        return f"{self.etudiant} - {self.programme} - {self.periode}"


class SelectionCours(models.Model):
    inscription = models.ForeignKey(
        InscriptionPedagogique,
        verbose_name="inscription",
        on_delete=models.CASCADE,
        related_name="cours_selectionnes",
    )
    cours = models.ForeignKey(
        "referentiels.Cours",
        verbose_name="cours",
        on_delete=models.PROTECT,
        related_name="selections_inscription",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("inscription", "cours"), name="uniq_selection_inscription_cours"
            )
        ]
        verbose_name = "cours selectionne"
        verbose_name_plural = "cours selectionnes"

    def clean(self):
        if self.inscription_id and self.cours_id:
            if self.inscription.programme_id != self.cours.programme_id:
                raise ValidationError(
                    "Le cours doit appartenir au programme de l'inscription."
                )
            if self.inscription.statut != InscriptionPedagogique.Statut.VALIDEE:
                raise ValidationError(
                    "Les cours ne peuvent etre choisis qu'apres validation de l'inscription."
                )
            if not self.inscription.periode.est_ouverte:
                raise ValidationError(
                    "La selection des cours est fermee pour cette periode."
                )

    def __str__(self):
        return f"{self.inscription.etudiant} - {self.cours}"


class TarifScolarite(models.Model):
    programme = models.ForeignKey(
        "referentiels.Programme",
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="tarifs_scolarite",
    )
    periode = models.ForeignKey(
        "referentiels.PeriodeAcademique",
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="tarifs_scolarite",
    )
    montant = models.DecimalField(
        "montant a payer",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    devise = models.CharField("devise ISO", max_length=3, default="HTG")
    est_actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ("periode", "programme__nom")
        constraints = [
            models.UniqueConstraint(
                fields=("programme", "periode"), name="uniq_tarif_programme_periode"
            )
        ]
        verbose_name = "tarif de scolarite"
        verbose_name_plural = "tarifs de scolarite"

    def clean(self):
        if self.programme_id and self.periode_id:
            if self.programme.entite_id != self.periode.entite_id:
                raise ValidationError(
                    {
                        "periode": "Le programme et la periode doivent appartenir a la meme entite."
                    }
                )

    def __str__(self):
        return f"{self.programme} - {self.periode}"


class PaiementScolarite(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "A verifier"
        VALIDE = "valide", "Valide"
        REFUSE = "refuse", "Refuse"

    etudiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="etudiant",
        on_delete=models.PROTECT,
        related_name="paiements_scolarite",
    )
    tarif = models.ForeignKey(
        TarifScolarite,
        verbose_name="tarif",
        on_delete=models.PROTECT,
        related_name="paiements",
    )
    montant = models.DecimalField(
        "montant paye",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reference = models.CharField("reference de paiement", max_length=100)
    date_paiement = models.DateField("date de paiement")
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="verifie par",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paiements_verifies",
    )
    date_validation = models.DateTimeField(
        "date de verification", null=True, blank=True
    )
    motif_refus = models.CharField("motif du refus", max_length=240, blank=True)
    date_creation = models.DateTimeField("date de declaration", auto_now_add=True)

    class Meta:
        ordering = ("statut", "-date_creation")
        constraints = [
            models.UniqueConstraint(
                fields=("tarif", "reference"), name="uniq_paiement_tarif_reference"
            ),
            models.CheckConstraint(
                check=models.Q(montant__gt=0), name="paiement_montant_positif"
            ),
        ]
        verbose_name = "paiement de scolarite"
        verbose_name_plural = "paiements de scolarite"

    def clean(self):
        erreurs = {}
        if self.etudiant_id and self.etudiant.role != self.etudiant.Role.ETUDIANT:
            erreurs["etudiant"] = "Le compte doit avoir le role etudiant."
        if self.etudiant_id and self.tarif_id:
            if self.etudiant.entite_id != self.tarif.programme.entite_id:
                erreurs["tarif"] = "Le tarif doit appartenir a l'entite de l'etudiant."
        if self.statut != self.Statut.EN_ATTENTE:
            if not self.valide_par_id:
                erreurs["valide_par"] = "Un utilisateur doit verifier ce paiement."
            elif not self.valide_par.is_superuser:
                if self.valide_par.role != self.valide_par.Role.PERSONNEL:
                    erreurs["valide_par"] = (
                        "Seul le registrariat peut verifier un paiement."
                    )
                elif self.valide_par.entite_id != self.tarif.programme.entite_id:
                    erreurs["valide_par"] = (
                        "Le registrariat doit appartenir a la meme entite."
                    )
        if self.statut == self.Statut.REFUSE and not self.motif_refus.strip():
            erreurs["motif_refus"] = "Le motif du refus est obligatoire."
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.etudiant} - {self.reference} - {self.get_statut_display()}"
