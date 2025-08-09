from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class DoctorManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, doctor_id, password=None, **extra_fields):
        if not doctor_id:
            raise ValueError('The Doctor ID must be set')
        extra_fields.setdefault('is_active', True)
        user = self.model(doctor_id=doctor_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, doctor_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(doctor_id, password, **extra_fields)


class Doctor(AbstractUser):
    username = None  # Remove default username
    doctor_id = models.CharField(max_length=6, unique=True)
    specialization = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)

    USERNAME_FIELD = 'doctor_id'
    REQUIRED_FIELDS = []  # Do not include 'username' here

    objects = DoctorManager()

    def __str__(self):
        return self.doctor_id



User = get_user_model()

class Patient(models.Model):
    doctor = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')])
    address = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.address:
            self.address = self.address.strip().title()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# --- NEW Prescription container model ---
class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription {self.id} - {self.patient.name} ({self.created_at.strftime('%Y-%m-%d')})"

class Problem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='problems')
    description = models.CharField(max_length=200)

    def save(self, *args, **kwargs):
        if self.description:
            self.description = self.description.strip().title()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description

class Examination(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='examinations')
    name = models.CharField(max_length=100, default='General Examination')  # Added with default
    description = models.CharField(max_length=200, blank=True, null=True)
    
    def __str__(self):
        return f"{self.name}: {self.description}"

class Report(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='reports')
    name = models.CharField(max_length=100)
    result = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.name}: {self.result}"

class ReportImage(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='report_images/')

class Medicine(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=100)
    strength = models.CharField(max_length=50, default="500mg")
    frequency = models.CharField(max_length=50, default="1+1+1")
    remark = models.CharField(max_length=100, default="After Eat")
    days = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} - {self.strength} ({self.frequency})"
