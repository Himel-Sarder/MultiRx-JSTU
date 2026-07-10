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


# --- Master medicine catalogue, imported from data/Medicines.csv ---
# Used to power the "type A, see medicines starting with A" autocomplete
# in the prescription form's Medicine Name field.
class MedicineMaster(models.Model):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    uses_raw = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# --- Research / CKD registry data (internal-only, never printed on the PDF) ---
class ClinicalResearchData(models.Model):
    """
    Extended research data collected on a dedicated 'Next' page after the
    prescription is created. This data is intentionally kept OUT of the
    prescription PDF template and is only used for internal record keeping
    and Excel export/filtering (research/registry purposes).
    """

    EDUCATION_CHOICES = [
        ('', 'Select'),
        ('Illiterate', 'Illiterate'),
        ('Primary', 'Primary'),
        ('Secondary', 'Secondary'),
        ('Higher Secondary', 'Higher Secondary'),
        ('Graduate', 'Graduate'),
        ('Postgraduate', 'Postgraduate'),
        ('Other', 'Other'),
    ]
    EMPLOYMENT_CHOICES = [
        ('', 'Select'),
        ('Employed', 'Employed'),
        ('Self-Employed', 'Self-Employed'),
        ('Unemployed', 'Unemployed'),
        ('Retired', 'Retired'),
        ('Student', 'Student'),
        ('Homemaker', 'Homemaker'),
        ('Other', 'Other'),
    ]
    SMOKING_CHOICES = [
        ('', 'Select'),
        ('Never', 'Never'),
        ('Former', 'Former'),
        ('Current', 'Current'),
    ]
    MODALITY_CHOICES = [
        ('', 'Select'),
        ('None', 'None / Pre-dialysis'),
        ('Hemodialysis', 'Hemodialysis (HD)'),
        ('Peritoneal Dialysis', 'Peritoneal Dialysis (PD)'),
        ('Transplantation', 'Transplantation'),
    ]
    VASCULAR_ACCESS_CHOICES = [
        ('', 'Select'),
        ('Fistula', 'Fistula'),
        ('Graft', 'Graft'),
        ('Catheter', 'Catheter'),
        ('N/A', 'N/A'),
    ]

    prescription = models.OneToOneField(
        Prescription, on_delete=models.CASCADE, related_name='research_data'
    )

    # 1. Education / Social
    education_level = models.CharField(max_length=30, choices=EDUCATION_CHOICES, blank=True)
    monthly_income = models.CharField(max_length=50, blank=True, help_text="Monthly income")
    employment_status = models.CharField(max_length=30, choices=EMPLOYMENT_CHOICES, blank=True)

    # 2. Clinical History & Comorbidities
    diagnosis = models.CharField(
        max_length=255, blank=True,
        help_text="Primary renal disease/cause of failure (e.g. ERA-PRD coding)"
    )
    comorbid_diabetes = models.BooleanField(default=False)
    comorbid_hypertension = models.BooleanField(default=False)
    comorbid_heart_failure = models.BooleanField(default=False)
    comorbid_ischemic_heart_disease = models.BooleanField(default=False)
    comorbid_peripheral_artery_disease = models.BooleanField(default=False)
    comorbid_stroke = models.BooleanField(default=False)

    smoking_status = models.CharField(max_length=20, choices=SMOKING_CHOICES, blank=True)
    bmi = models.CharField(max_length=20, blank=True)
    weight = models.CharField(max_length=20, blank=True, help_text="Weight (kg)")
    height = models.CharField(max_length=20, blank=True, help_text="Height (cm)")

    # 3. Laboratory Values & Kidney Function
    serum_creatinine = models.CharField(max_length=20, blank=True)
    cystatin_c = models.CharField(max_length=20, blank=True)
    egfr = models.CharField(max_length=20, blank=True, verbose_name="eGFR")
    uacr = models.CharField(max_length=20, blank=True, verbose_name="uACR")
    protein_levels = models.CharField(max_length=20, blank=True)
    hemoglobin = models.CharField(max_length=20, blank=True)
    ferritin = models.CharField(max_length=20, blank=True)
    calcium = models.CharField(max_length=20, blank=True)
    phosphorus = models.CharField(max_length=20, blank=True)
    pth = models.CharField(max_length=20, blank=True, verbose_name="PTH")
    potassium = models.CharField(max_length=20, blank=True)
    bicarbonate = models.CharField(max_length=20, blank=True)
    serum_albumin = models.CharField(max_length=20, blank=True)
    crp = models.CharField(max_length=20, blank=True, verbose_name="CRP")
    total_cholesterol = models.CharField(max_length=20, blank=True)
    hba1c = models.CharField(max_length=20, blank=True, verbose_name="HbA1c")

    # 4. Kidney Replacement Therapy (KRT) Data
    krt_modality = models.CharField(max_length=30, choices=MODALITY_CHOICES, blank=True)
    krt_initiation_date = models.DateField(null=True, blank=True)
    modality_change_dates = models.CharField(max_length=255, blank=True, help_text="Dates of modality changes")
    transplant_date = models.DateField(null=True, blank=True)
    dialysis_duration = models.CharField(max_length=50, blank=True, help_text="e.g. 4 hours/session")
    dialysis_frequency = models.CharField(max_length=50, blank=True, help_text="e.g. 3x/week")
    vascular_access_type = models.CharField(max_length=20, choices=VASCULAR_ACCESS_CHOICES, blank=True)

    # 5. Medication Data
    med_esa = models.BooleanField(default=False, verbose_name="ESA (Erythropoietin-stimulating agents)")
    med_iron = models.BooleanField(default=False, verbose_name="Iron")
    med_phosphate_binders = models.BooleanField(default=False, verbose_name="Phosphate binders")
    med_vitamin_d = models.BooleanField(default=False, verbose_name="Vitamin D")
    med_calcimimetics = models.BooleanField(default=False, verbose_name="Calcimimetics")
    med_ace_arb = models.BooleanField(default=False, verbose_name="Antihypertensives (ACE inhibitors/ARBs)")
    med_diuretics = models.BooleanField(default=False, verbose_name="Diuretics")
    med_statins = models.BooleanField(default=False, verbose_name="Statins")
    med_immunosuppressives = models.BooleanField(default=False, verbose_name="Immunosuppressives")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_bmi(self):
        """
        Auto-calculate BMI from weight (kg) and height (cm).
        BMI = weight(kg) / (height(m) ** 2)
        Returns the value rounded to 1 decimal place, or None if
        weight/height are missing or not valid numbers.
        This is a server-side fallback for when the field is auto-filled
        by JS on the form (research_data.html) but also covers cases
        where the record is created/edited outside the browser (e.g. admin, shell).
        """
        try:
            weight_kg = float(str(self.weight).strip())
            height_cm = float(str(self.height).strip())
            if weight_kg <= 0 or height_cm <= 0:
                return None
            height_m = height_cm / 100
            return round(weight_kg / (height_m ** 2), 1)
        except (TypeError, ValueError):
            return None

    def save(self, *args, **kwargs):
        # Auto-calculate BMI whenever weight/height are present, so the
        # stored value always stays in sync even if it wasn't computed on
        # the client side (e.g. JS disabled, admin edits, API usage).
        computed = self.calculate_bmi()
        if computed is not None:
            self.bmi = str(computed)
        super().save(*args, **kwargs)

    def comorbidities_list(self):
        mapping = [
            (self.comorbid_diabetes, "Diabetes"),
            (self.comorbid_hypertension, "Hypertension"),
            (self.comorbid_heart_failure, "Heart Failure"),
            (self.comorbid_ischemic_heart_disease, "Ischemic Heart Disease"),
            (self.comorbid_peripheral_artery_disease, "Peripheral Artery Disease"),
            (self.comorbid_stroke, "Stroke"),
        ]
        return [label for present, label in mapping if present]

    def kidney_medications_list(self):
        mapping = [
            (self.med_esa, "ESA"),
            (self.med_iron, "Iron"),
            (self.med_phosphate_binders, "Phosphate binders"),
            (self.med_vitamin_d, "Vitamin D"),
            (self.med_calcimimetics, "Calcimimetics"),
        ]
        return [label for present, label in mapping if present]

    def cardiovascular_medications_list(self):
        mapping = [
            (self.med_ace_arb, "ACE inhibitors/ARBs"),
            (self.med_diuretics, "Diuretics"),
            (self.med_statins, "Statins"),
            (self.med_immunosuppressives, "Immunosuppressives"),
        ]
        return [label for present, label in mapping if present]

    def __str__(self):
        return f"Research Data - Prescription {self.prescription_id}"
