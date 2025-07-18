import re
from django.contrib.auth.models import AbstractUser
from django.db import models
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

    # ↓ NEW: always normalise address
    def save(self, *args, **kwargs):
        if self.address:
            self.address = self.address.strip().title()  # e.g. "  sHerPuR " -> "Sherpur"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Problem(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='problems')
    description = models.CharField(max_length=200)

    # ↓ NEW: always normalise description
    def save(self, *args, **kwargs):
        if self.description:
            self.description = self.description.strip().title()  # e.g. "  sHerPuR " -> "Sherpur"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description


class Examination(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='examinations')
    description = models.CharField(max_length=200)

    def __str__(self):
        return self.description


class Report(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reports')
    name = models.CharField(max_length=100)
    result = models.CharField(max_length=200)

class ReportImage(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='report_images/')

class Medicine(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=100)
    strength = models.CharField(max_length=50, default="500mg")   # NEW
    frequency = models.CharField(max_length=50, default="1+1+1")  # NEW
    remark = models.CharField(max_length=100, default="After Eat") # NEW
    days = models.PositiveIntegerField()

    
    def __str__(self):
        return f"{self.name} - {self.strength} ({self.frequency})"


class MedicineMaster(models.Model):
    """
    ONE row per brand/generic in your CSV.
    `keywords` is a comma‑separated list of lower‑case words
    we’ll search against when the doctor types a problem.
    """
    name     = models.CharField(max_length=120, unique=True)
    uses_raw = models.TextField()                     # the human sentence
    keywords = models.TextField()                     # auto‑generated

    def save(self, *args, **kwargs):
        # on save, normalise & generate keywords once
        self.name = self.name.strip().title()
        # simple keyword extraction ⇢ split on space / comma
        words = {
            w.strip().lower()
            for w in re.split(r"[,\s]+", self.uses_raw)
            if len(w) > 2                                  # skip “of”, “in”…  
        }
        self.keywords = ",".join(sorted(words))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
