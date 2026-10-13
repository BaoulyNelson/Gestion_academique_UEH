from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("administration", "0002_initial")]

    operations = [
        migrations.AlterField(
            model_name="journalaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("VALIDATION", "Validation"),
                    ("REJET", "Rejet"),
                    ("SUPPRESSION", "Suppression"),
                    ("AFFECTATION_SALLE", "Affectation de salle"),
                ],
                max_length=20,
                verbose_name="action",
            ),
        ),
    ]
