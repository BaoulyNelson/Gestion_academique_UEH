from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("candidats", "0004_candidat_nationalite_identifiants_responsable")]

    operations = [
        migrations.CreateModel(
            name="EcoleCandidat",
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
                    "nom",
                    models.CharField(max_length=200, verbose_name="nom de l’école"),
                ),
                (
                    "zone",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="commune"
                    ),
                ),
                (
                    "certificat",
                    models.FileField(
                        upload_to="dossiers_candidats/ecoles/%Y/%m/",
                        verbose_name="certificat scolaire",
                    ),
                ),
                (
                    "date_ajout",
                    models.DateTimeField(auto_now_add=True, verbose_name="ajouté le"),
                ),
                (
                    "candidat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ecoles",
                        to="candidats.candidat",
                        verbose_name="candidat",
                    ),
                ),
            ],
            options={
                "verbose_name": "école de candidat",
                "verbose_name_plural": "écoles du candidat",
                "ordering": ["-date_ajout", "pk"],
            },
        ),
        migrations.CreateModel(
            name="ParcoursCandidat",
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
                    "etablissement",
                    models.CharField(
                        max_length=200,
                        verbose_name="établissement d’enseignement supérieur",
                    ),
                ),
                (
                    "niveau",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LICENCE", "Licence"),
                            ("MASTER", "Master"),
                            ("DOCTORAT", "Doctorat"),
                            ("AUTRE", "Autre"),
                        ],
                        max_length=12,
                        verbose_name="niveau",
                    ),
                ),
                (
                    "programme",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="programme"
                    ),
                ),
                (
                    "annee_obtention",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="année d’obtention"
                    ),
                ),
                (
                    "type_document",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        verbose_name="type de diplôme ou relevé",
                    ),
                ),
                (
                    "certificat",
                    models.FileField(
                        blank=True,
                        upload_to="dossiers_candidats/etudes/%Y/%m/",
                        verbose_name="certificat ou relevé de notes",
                    ),
                ),
                (
                    "lettre_recommandation",
                    models.FileField(
                        blank=True,
                        upload_to="dossiers_candidats/etudes/%Y/%m/",
                        verbose_name="lettre de recommandation",
                    ),
                ),
                (
                    "lettre_motivation",
                    models.FileField(
                        blank=True,
                        upload_to="dossiers_candidats/etudes/%Y/%m/",
                        verbose_name="lettre de motivation",
                    ),
                ),
                (
                    "cv_ou_autre_document",
                    models.FileField(
                        blank=True,
                        upload_to="dossiers_candidats/etudes/%Y/%m/",
                        verbose_name="CV ou autre document",
                    ),
                ),
                (
                    "date_ajout",
                    models.DateTimeField(auto_now_add=True, verbose_name="ajouté le"),
                ),
                (
                    "candidat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parcours_etudes",
                        to="candidats.candidat",
                        verbose_name="candidat",
                    ),
                ),
            ],
            options={
                "verbose_name": "parcours d’études supérieures",
                "verbose_name_plural": "parcours d’études supérieures",
                "ordering": ["-date_ajout", "pk"],
            },
        ),
    ]
