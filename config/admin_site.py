from django.contrib.admin import AdminSite


class AdministrationGP7Site(AdminSite):
    site_header = "GP7 | Administration"
    site_title = "Administration GP7"
    index_title = "Gestion academique"

    def has_permission(self, request):
        return request.user.is_active and request.user.is_superuser
