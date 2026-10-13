from decimal import Decimal

from django.db.models import Sum

from applications.inscriptions.models import PaiementScolarite, TarifScolarite


def montant_scolarite_confirme(etudiant, tarif: TarifScolarite) -> Decimal:
    total = PaiementScolarite.objects.filter(
        etudiant=etudiant,
        tarif=tarif,
        statut=PaiementScolarite.Statut.VALIDE,
    ).aggregate(total=Sum("montant"))["total"]
    return total or Decimal("0.00")


def frais_scolarite_acquittes(etudiant, tarif: TarifScolarite) -> bool:
    return montant_scolarite_confirme(etudiant, tarif) >= tarif.montant
