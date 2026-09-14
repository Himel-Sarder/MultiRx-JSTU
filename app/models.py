import re

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Max
from django.utils import timezone


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
# There is no public registration. Three kinds of accounts exist:
#   * Doctor       - login ID starts with "HF" + 4 digits  (e.g. HF1234)
#   * Receptionist - login ID starts with "RE" + 4 digits  (e.g. RE1234)
#   * Administrator- any other ID, created with role="admin" (e.g. admin-RX)
# For the two clinic roles the prefix of the ID decides which console opens, so
# the role is always derived from the ID itself. Administrator IDs are free-form
# and keep whatever role they were created with, which is how the admin panel is
# reached instead of a doctor/reception console.

ROLE_DOCTOR = 'doctor'
ROLE_RECEPTIONIST = 'receptionist'
ROLE_ADMIN = 'admin'

ROLE_CHOICES = [
    (ROLE_DOCTOR, 'Doctor'),
    (ROLE_RECEPTIONIST, 'Receptionist'),
    (ROLE_ADMIN, 'Administrator'),
]

DOCTOR_ID_PREFIX = 'HF'
RECEPTIONIST_ID_PREFIX = 'RE'

# Login IDs are stored as typed; only the clinic formats are normalised to caps.
LOGIN_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$')


def role_for_user_id(user_id):
    """Return the clinic role implied by a login ID, or None when the ID is not
    in a clinic format (administrator IDs fall into this second case, and keep
    the role stored on the account)."""
    if not user_id:
        return None
    user_id = user_id.strip().upper()
    if len(user_id) != 6 or not user_id[2:].isdigit():
        return None
    if user_id.startswith(DOCTOR_ID_PREFIX):
        return ROLE_DOCTOR
    if user_id.startswith(RECEPTIONIST_ID_PREFIX):
        return ROLE_RECEPTIONIST
    return None


def normalize_login_id(user_id):
    """Clinic IDs (HF1234 / RE0007) are case-insensitive and stored uppercase.
    Administrator IDs keep the exact casing they were created with."""
    if not user_id:
        return user_id
    cleaned = user_id.strip()
    return cleaned.upper() if role_for_user_id(cleaned) else cleaned


class DoctorManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, doctor_id, password=None, **extra_fields):
        if not doctor_id:
            raise ValueError('The Login ID must be set')
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

    def doctors(self):
        return self.filter(role=ROLE_DOCTOR, is_active=True)

    def receptionists(self):
        return self.filter(role=ROLE_RECEPTIONIST, is_active=True)

    def admins(self):
        return self.filter(role=ROLE_ADMIN, is_active=True)


class Doctor(AbstractUser):
    """Single account model for every role (kept named `Doctor` because it is
    wired up as AUTH_USER_MODEL). For clinic accounts `role` is derived from the
    login ID prefix; administrator accounts carry role="admin" explicitly."""

    username = None  # Remove default username
    doctor_id = models.CharField(max_length=32, unique=True, verbose_name='Login ID')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_DOCTOR)
    specialization = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)

    USERNAME_FIELD = 'doctor_id'
    REQUIRED_FIELDS = []  # Do not include 'username' here

    objects = DoctorManager()

    def save(self, *args, **kwargs):
        self.doctor_id = normalize_login_id(self.doctor_id)
        # A clinic-format ID always dictates the role; other IDs keep theirs.
        derived = role_for_user_id(self.doctor_id)
        if derived:
            self.role = derived
        super().save(*args, **kwargs)

    @property
    def is_doctor(self):
        return self.role == ROLE_DOCTOR

    @property
    def is_receptionist(self):
        return self.role == ROLE_RECEPTIONIST

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def role_label(self):
        return dict(ROLE_CHOICES).get(self.role, 'User')

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.doctor_id

    @property
    def display_name(self):
        """'Dr. Jane Doe' for doctors, plain name for everyone else."""
        name = f"{self.first_name} {self.last_name}".strip()
        if not name:
            return self.doctor_id
        if self.is_doctor and not name.lower().startswith(('dr.', 'dr ', 'prof')):
            return f"Dr. {name}"
        return name

    def __str__(self):
        return f"{self.doctor_id} ({self.role_label})"


User = get_user_model()


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

class Patient(models.Model):
    # `doctor` is the doctor this patient is registered under / consults.
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patients')
    # Receptionists create most patient records; keep who did it for the audit trail.
    registered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='registered_patients'
    )
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')])
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.address:
            self.address = self.address.strip().title()
        super().save(*args, **kwargs)

    @property
    def formatted_id(self):
        return f"P{self.id:04d}"

    def __str__(self):
        return self.name


# --- NEW Prescription container model ---
class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    doctor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prescriptions'
    )
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


# ---------------------------------------------------------------------------
# Appointments / patient queue
# ---------------------------------------------------------------------------

class Appointment(models.Model):
    """One queue entry for one patient on one day with one doctor.

    Flow: receptionist registers/looks up the patient and places them in the
    queue (serial 1, 2, 3, ...). The doctor consults the patient at the front
    of the queue, then presses "Next Patient", which rings the reception desk;
    the receptionist then sends the next waiting patient in."""

    STATUS_WAITING = 'waiting'
    STATUS_IN_CONSULTATION = 'in_consultation'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting'),
        (STATUS_IN_CONSULTATION, 'In Consultation'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_appointments'
    )
    prescription = models.ForeignKey(
        Prescription, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='appointments'
    )

    date = models.DateField(default=timezone.localdate)
    serial = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    note = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['date', 'serial']
        unique_together = ('doctor', 'date', 'serial')

    @classmethod
    def next_serial(cls, doctor, date=None):
        date = date or timezone.localdate()
        current = cls.objects.filter(doctor=doctor, date=date).aggregate(m=Max('serial'))['m']
        return (current or 0) + 1

    @property
    def is_active(self):
        return self.status in (self.STATUS_WAITING, self.STATUS_IN_CONSULTATION)

    @property
    def status_label(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def __str__(self):
        return f"#{self.serial} {self.patient.name} - {self.date} ({self.status_label})"


class PatientCall(models.Model):
    """Raised when a doctor presses "Next Patient". The reception desk polls
    for unacknowledged calls, rings a 3-second bell, and acknowledges the call
    by sending the next waiting patient in."""

    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_calls')
    finished_appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calls'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acknowledged_calls'
    )

    class Meta:
        ordering = ['-created_at']

    def acknowledge(self, user=None):
        self.acknowledged = True
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save(update_fields=['acknowledged', 'acknowledged_at', 'acknowledged_by'])

    def __str__(self):
        return f"Call from {self.doctor.doctor_id} at {self.created_at:%H:%M:%S}"


# --- Research / CKD registry data (internal-only, never printed on the PDF) ---
class ClinicalResearchData(models.Model):
    """
    Extended patient record ("Additional Patient Record") collected by the
    receptionist when the patient is registered. This data is intentionally
    kept OUT of the prescription PDF template and is only used for internal
    record keeping and Excel export/filtering (research/registry purposes).
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

    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name='research_data'
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
        by JS on the form but also covers cases where the record is
        created/edited outside the browser (e.g. admin, shell).
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

    def has_any_data(self):
        """True when at least one meaningful field has been filled in."""
        skip = {'id', 'patient', 'created_at', 'updated_at'}
        for field in self._meta.fields:
            if field.name in skip:
                continue
            value = getattr(self, field.name)
            if isinstance(value, bool):
                if value:
                    return True
            elif value not in (None, ''):
                return True
        return False

    def __str__(self):
        return f"Additional Record - {self.patient.name}"
