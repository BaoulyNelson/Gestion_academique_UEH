from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.functional import cached_property


class GestionnaireUtilisateur(UserManager):
    use_in_migrations = True

    def create_user(self, username=None, email=None, password=None, **extra_fields):
        if (
            username
            and "@" in username
            and email
            and "@" not in email
            and password is None
        ):
            password, email, username = email, username, None
        if email and not username:
            username = self._username_for_email(email)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        if (
            username
            and "@" in username
            and email
            and "@" not in email
            and password is None
        ):
            password, email, username = email, username, None
        if email and not username:
            username = self._username_for_email(email)
        return super().create_superuser(username, email, password, **extra_fields)

    def _username_for_email(self, email):
        base = self.model.normalize_username(email.split("@", 1)[0])[:140] or "user"
        username = base
        suffix = 1
        while self.model._default_manager.filter(username=username).exists():
            username = f"{base[:140]}-{suffix}"
            suffix += 1
        return username


class SiteConfiguration(models.Model):
    nom_site = models.CharField("nom du site", max_length=120, default="GP7")
    slogan = models.CharField("slogan", max_length=180, default="Gestion academique")
    logo = models.ImageField("logo", upload_to="site/logo/", blank=True, null=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    email_contact = models.EmailField("email de contact", blank=True, default="")
    adresse = models.CharField("adresse", max_length=255, blank=True, default="")
    texte_pied_page = models.TextField("texte du pied de page", blank=True, default="")
    date_maj = models.DateTimeField("date de mise a jour", auto_now=True)

    class Meta:
        verbose_name = "configuration du site"
        verbose_name_plural = "configurations du site"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.order_by("pk").first()
        if obj is None:
            obj = cls.objects.create(
                nom_site="GP7",
                slogan="Gestion academique",
            )
        return obj

    def __str__(self):
        return self.nom_site


class Utilisateur(AbstractUser):
    class Role(models.TextChoices):
        ADMINISTRATEUR = "administrateur", "Administrateur"
        PERSONNEL = "personnel", "Personnel du secretariat ou registrariat"
        PROFESSEUR = "professeur", "Professeur"
        ETUDIANT = "etudiant", "Etudiant"

    email = models.EmailField("adresse courriel", unique=True)
    prenom = models.CharField("prénom", max_length=100, blank=True)
    nom = models.CharField("nom", max_length=100, blank=True)
    role = models.CharField(
        "role GP7",
        max_length=24,
        choices=Role.choices,
        default=Role.ETUDIANT,
    )
    entite = models.ForeignKey(
        "referentiels.Entite",
        verbose_name="entite de rattachement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="utilisateurs",
    )
    photo_profil = models.ImageField(
        "photo de profil",
        upload_to="utilisateurs/photos/",
        blank=True,
        null=True,
    )
    objects = GestionnaireUtilisateur()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            for champ_admission, champ_gp7 in (
                ("prenom", "first_name"),
                ("nom", "last_name"),
            ):
                if champ_admission in update_fields and champ_gp7 not in update_fields:
                    setattr(self, champ_gp7, getattr(self, champ_admission))
                    update_fields.add(champ_gp7)
                elif champ_gp7 in update_fields:
                    setattr(self, champ_admission, getattr(self, champ_gp7))
                    update_fields.add(champ_admission)
            kwargs["update_fields"] = update_fields
        elif self._state.adding:
            self.first_name = self.first_name or self.prenom
            self.last_name = self.last_name or self.nom
            self.prenom = self.prenom or self.first_name
            self.nom = self.nom or self.last_name
        else:
            self.prenom = self.first_name
            self.nom = self.last_name
        if self.is_superuser:
            self.role = self.Role.ADMINISTRATEUR
        super().save(*args, **kwargs)

    @cached_property
    def est_administrateur_entite(self):
        from applications.entites.models import entites_autorisees

        entites = entites_autorisees(self)
        return entites is None or entites.exists()

    def __str__(self):
        return self.get_full_name() or self.username


class ProfilEtudiant(models.Model):
    class Sexe(models.TextChoices):
        FEMININ = "feminin", "Feminin"
        MASCULIN = "masculin", "Masculin"
        AUTRE = "autre", "Autre"
        NON_RENSEIGNE = "non_renseigne", "Non renseigne"

    utilisateur = models.OneToOneField(
        Utilisateur,
        verbose_name="compte etudiant",
        on_delete=models.CASCADE,
        related_name="profil_etudiant",
    )
    code_etudiant = models.CharField(
        "code etudiant",
        max_length=48,
        unique=True,
        null=True,
        blank=True,
        help_text="Le format officiel sera renseigne par la DReg.",
    )
    nif = models.CharField("NIF", max_length=40, blank=True)
    cin = models.CharField("CIN", max_length=40, blank=True)
    sexe = models.CharField(
        "sexe",
        max_length=16,
        choices=Sexe.choices,
        default=Sexe.NON_RENSEIGNE,
    )
    date_naissance = models.DateField("date de naissance", null=True, blank=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    adresse = models.TextField("adresse", blank=True)
    photo = models.ImageField(
        "photo d'identite",
        upload_to="etudiants/photos/",
        blank=True,
    )
    date_creation = models.DateTimeField("date de creation", auto_now_add=True)

    class Meta:
        ordering = ("utilisateur__last_name", "utilisateur__first_name")
        verbose_name = "profil etudiant"
        verbose_name_plural = "profils etudiants"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.utilisateur_id and self.utilisateur.role != Utilisateur.Role.ETUDIANT:
            raise ValidationError(
                {"utilisateur": "Le profil doit etre associe a un compte etudiant."}
            )

    def __str__(self):
        return self.code_etudiant or str(self.utilisateur)
