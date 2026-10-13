from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("candidatures", "0003_rendre_numero_et_rang_obligatoires"),
        ("candidats", "0003_candidat_departement_geographique_candidat_sexe"),
        ("entites", "0002_entite_email_contact_entite_inscription_ouverte"),
    ]

    operations = [
        migrations.CreateModel(
            name="BrouillonInscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "annee_academique",
                    models.CharField(
                        blank=True, max_length=9, verbose_name="année académique"
                    ),
                ),
                (
                    "horaire",
                    models.CharField(
                        blank=True,
                        choices=[("AM", "Matin"), ("PM", "Après-midi")],
                        max_length=2,
                        verbose_name="horaire",
                    ),
                ),
                (
                    "date_modification",
                    models.DateTimeField(auto_now=True, verbose_name="modifié le"),
                ),
                (
                    "candidat",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="brouillon_inscription",
                        to="candidats.candidat",
                        verbose_name="candidat",
                    ),
                ),
                (
                    "entite",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="brouillons_inscription",
                        to="entites.entite",
                        verbose_name="entité",
                    ),
                ),
                (
                    "option",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="brouillons_inscription",
                        to="entites.option",
                        verbose_name="option",
                    ),
                ),
            ],
            options={
                "verbose_name": "brouillon d’inscription",
                "verbose_name_plural": "brouillons d’inscription",
            },
        ),
    ]
