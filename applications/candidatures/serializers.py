from rest_framework import serializers

from applications.candidatures.models import Inscription


class SerializeurInscription(serializers.ModelSerializer):
    class Meta:
        model = Inscription
        fields = [
            "id",
            "numero_dossier",
            "entite",
            "option",
            "annee_academique",
            "horaire",
            "date_inscription",
            "salle",
            "statut",
            "rang",
        ]
        read_only_fields = fields
