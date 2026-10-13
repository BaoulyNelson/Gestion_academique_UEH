from django import forms

from applications.documents.models import DocumentCandidat


class DocumentCandidatForm(forms.ModelForm):
    class Meta:
        model = DocumentCandidat
        fields = ["type_document", "fichier"]
        widgets = {
            "type_document": forms.Select(attrs={"class": "form-select"}),
            "fichier": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
            ),
        }
