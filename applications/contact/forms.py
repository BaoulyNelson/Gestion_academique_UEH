from django import forms


class FormulaireContact(forms.Form):
    nom = forms.CharField(
        label="Nom complet",
        max_length=120,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        error_messages={"invalid": "Saisissez une adresse e-mail valide."},
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    sujet = forms.CharField(
        label="Sujet",
        max_length=160,
        widget=forms.TextInput(),
    )
    message = forms.CharField(
        label="Votre message",
        widget=forms.Textarea(attrs={"rows": 6}),
    )
