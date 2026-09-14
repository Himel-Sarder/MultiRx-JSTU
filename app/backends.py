from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class LoginIDBackend(ModelBackend):
    """Authenticate against the login ID (HF#### for doctors, RE#### for
    receptionists) instead of a username."""

    def authenticate(self, request, doctor_id=None, password=None, **kwargs):
        login_id = doctor_id or kwargs.get('user_id') or kwargs.get('username')
        if not login_id or password is None:
            return None

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(doctor_id__iexact=login_id.strip())
        except UserModel.DoesNotExist:
            # Run the default hasher once so a missing account takes about the
            # same time as a wrong password (avoids user enumeration by timing).
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


# Backwards-compatible alias for the old settings entry.
DoctorIDBackend = LoginIDBackend
