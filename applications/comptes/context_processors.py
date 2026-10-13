from .models import SiteConfiguration


def site_config(request):
    config = SiteConfiguration.get_solo()
    return {
        "site_config": config,
        "site_name": config.nom_site,
        "site_slogan": config.slogan,
        "site_logo": config.logo,
        "site_phone": config.telephone,
        "site_email": config.email_contact,
        "site_address": config.adresse,
        "site_footer": config.texte_pied_page,
    }