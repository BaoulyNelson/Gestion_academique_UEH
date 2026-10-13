from django.db import migrations, models


def completer_numeros_dossier(apps, schema_editor):
    Inscription = apps.get_model("candidatures", "Inscription")
    base = Inscription.objects.using(schema_editor.connection.alias)
    candidats = base.order_by().values_list("candidat_id", flat=True).distinct()

    for candidat_id in candidats.iterator():
        inscriptions = list(
            base.filter(candidat_id=candidat_id).order_by("date_inscription", "pk")
        )
        if len(inscriptions) > 3:
            raise RuntimeError(
                f"Migration impossible : le candidat {candidat_id} possède plus de trois inscriptions."
            )

        rangs_utilises = {
            inscription.rang
            for inscription in inscriptions
            if inscription.rang is not None
        }
        for inscription in inscriptions:
            if inscription.rang is None:
                inscription.rang = next(
                    rang for rang in range(3) if rang not in rangs_utilises
                )
                rangs_utilises.add(inscription.rang)

            numero_attendu = candidat_id * 100 + inscription.rang
            if (
                inscription.numero_dossier is not None
                and inscription.numero_dossier != numero_attendu
            ):
                raise RuntimeError(
                    f"Migration impossible : le dossier {inscription.pk} ne respecte pas sa formule de numérotation."
                )
            if inscription.numero_dossier is None:
                inscription.numero_dossier = numero_attendu
                inscription.save(update_fields=["numero_dossier", "rang"])
            elif inscription.rang is not None:
                inscription.save(update_fields=["rang"])


class Migration(migrations.Migration):
    dependencies = [("candidatures", "0002_initial")]

    operations = [
        migrations.RunPython(completer_numeros_dossier, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="inscription",
            name="numero_dossier",
            field=models.PositiveBigIntegerField(
                editable=False, unique=True, verbose_name="numéro de dossier"
            ),
        ),
        migrations.AlterField(
            model_name="inscription",
            name="rang",
            field=models.PositiveSmallIntegerField(editable=False, verbose_name="rang"),
        ),
    ]
