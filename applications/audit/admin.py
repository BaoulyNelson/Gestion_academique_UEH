from django.contrib import admin

from .models import JournalAction


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display = (
        "date_creation",
        "utilisateur",
        "action",
        "type_objet",
        "identifiant_objet",
    )
    list_filter = ("action", "type_objet", "date_creation")
    search_fields = (
        "utilisateur__username",
        "action",
        "type_objet",
        "identifiant_objet",
    )
    readonly_fields = tuple(field.name for field in JournalAction._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
