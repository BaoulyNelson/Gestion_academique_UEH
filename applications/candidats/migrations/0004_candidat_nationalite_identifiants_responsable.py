from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("candidats", "0003_candidat_departement_geographique_candidat_sexe")
    ]

    operations = [
        migrations.AddField(
            model_name="candidat",
            name="nationalite",
            field=models.CharField(
                default="Haïtienne", max_length=80, verbose_name="nationalité"
            ),
        ),
        migrations.AddField(
            model_name="candidat",
            name="nom_parent_responsable",
            field=models.CharField(
                blank=True, max_length=200, verbose_name="nom du parent ou responsable"
            ),
        ),
        migrations.AddField(
            model_name="candidat",
            name="nif",
            field=models.CharField(blank=True, max_length=30, verbose_name="NIF"),
        ),
        migrations.AddField(
            model_name="candidat",
            name="ninu",
            field=models.CharField(blank=True, max_length=30, verbose_name="NINU"),
        ),
    ]
