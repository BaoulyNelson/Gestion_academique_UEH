from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("referentiels", "0002_affectationcours_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="periodeacademique",
            name="type_periode",
            field=models.CharField(
                choices=[
                    ("annee", "Annee"),
                    ("session", "Session"),
                    ("trimestre", "Trimestre"),
                    ("semestre", "Semestre"),
                    ("quadrimestre", "Quadrimestre"),
                    ("niveau", "Niveau"),
                ],
                max_length=16,
                verbose_name="type de periode",
            ),
        ),
    ]
