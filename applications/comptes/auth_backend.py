from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        identifier = (username or "").strip()
        if not identifier or not password:
            return None

        user = (
            UserModel._default_manager.filter(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            )
            .order_by("pk")
            .first()
        )

        if (
            user is not None
            and user.check_password(password)
            and self.user_can_authenticate(user)
        ):
            return user

        return None
