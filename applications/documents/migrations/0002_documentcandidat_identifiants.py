from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="documentcandidat",
            name="type_document",
            field=models.CharField(
                choices=[
                    ("NAISSANCE", "Certificat de naissance"),
                    ("PHOTO", "Photo d’identité"),
                    ("DIPLOME", "Diplôme ou relevé de notes"),
                    ("PAIEMENT", "Fiche de paiement"),
                    ("NIF", "Document NIF"),
                    ("NINU", "Document NINU"),
                    ("AUTRE", "Autre document"),
                ],
                max_length=12,
                verbose_name="type de document",
            ),
        ),
    ]
