from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model

class Doctor(AbstractUser):
    doctor_id = models.CharField(max_length=6, unique=True)
    specialization = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.doctor_id})"

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
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='examinations', null=True, blank=True)
    description = models.CharField(max_length=200)

    def __str__(self):
        return self.description

class Report(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='reports')
    name = models.CharField(max_length=100)
    result = models.CharField(max_length=200)

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
