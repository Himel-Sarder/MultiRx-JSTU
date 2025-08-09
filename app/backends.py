from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class DoctorIDBackend(ModelBackend):
    def authenticate(self, request, doctor_id=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(doctor_id=doctor_id)
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            return None