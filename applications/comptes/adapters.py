from allauth.account.adapter import DefaultAccountAdapter


class AdaptateurCompteAdmission(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        utilisateur = super().save_user(request, user, form, commit)
        if commit:
            from applications.candidats.models import Candidat

            Candidat.objects.get_or_create(utilisateur=utilisateur)
        return utilisateur
