from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import (
    ROLE_ADMIN,
    ROLE_CHOICES,
    ClinicalResearchData,
    Doctor,
    LOGIN_ID_RE,
    Patient,
    normalize_login_id,
    role_for_user_id,
)


INPUT_CLASS = ('w-full px-4 py-2.5 border border-slate-300 rounded-lg bg-slate-50 '
               'text-slate-800 placeholder-slate-400 transition '
               'focus:outline-none focus:bg-white focus:border-emerald-500 '
               'focus:ring-2 focus:ring-emerald-500/20')


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class LoginForm(forms.Form):
    """Single login form for both roles. The ID prefix (HF / RE) decides which
    system the user is taken to after signing in."""

    doctor_id = forms.CharField(
        max_length=32,
        label="Login ID",
        widget=forms.TextInput(attrs={
            'placeholder': 'HF1234, RE1234 or your admin ID',
            'autocomplete': 'username',
            'autocapitalize': 'off',
            'autocorrect': 'off',
            'spellcheck': 'false',
            'class': INPUT_CLASS,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
            'class': INPUT_CLASS,
        }),
        label="Password"
    )

    def clean_doctor_id(self):
        # Only reject IDs that could not belong to any account; whether the ID
        # actually exists is answered by authentication, so a wrong ID and a
        # wrong password produce the same message.
        login_id = (self.cleaned_data.get('doctor_id') or '').strip()
        if not LOGIN_ID_RE.match(login_id):
            raise forms.ValidationError("Enter a valid login ID.")
        return normalize_login_id(login_id)


# Kept under the old name so any lingering imports keep working.
DoctorLoginForm = LoginForm


class AccountCreationForm(UserCreationForm):
    """Admin-side account creation. Django's stock UserCreationForm targets a
    `username` field, which this project replaced with `doctor_id`."""

    class Meta:
        model = Doctor
        fields = ('doctor_id', 'first_name', 'last_name')

    def clean_doctor_id(self):
        return clean_new_login_id(self.cleaned_data.get('doctor_id'))


class AccountChangeForm(forms.ModelForm):
    """Admin-side account edit form (the role follows the ID prefix on save)."""

    class Meta:
        model = Doctor
        fields = '__all__'


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['profile_picture', 'first_name', 'last_name', 'email',
                  'phone', 'bio', 'specialization']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'name@example.com'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Contact number'}),
            'bio': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4, 'placeholder': 'Short bio'}),
            'specialization': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. Nephrologist'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_picture'].widget.attrs.update({
            'accept': 'image/*',
            'class': 'hidden',
        })
        # Only doctors have a medical specialization.
        if self.instance and not self.instance.is_doctor:
            self.fields.pop('specialization', None)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance


DoctorProfileUpdateForm = ProfileUpdateForm


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['profile_picture']

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            # Validate file size (2MB max)
            if picture.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 2MB )")

            # Validate file type
            valid_types = ['image/jpeg', 'image/png', 'image/gif']
            content_type = getattr(picture, 'content_type', None)
            if content_type and content_type not in valid_types:
                raise forms.ValidationError("Only JPEG, PNG or GIF images are allowed")

        return picture


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

class PatientForm(forms.ModelForm):
    """Core patient demographics. Used by the receptionist's New Patient page
    and shown read-only to the doctor on the prescription page."""

    class Meta:
        model = Patient
        fields = ['name', 'age', 'gender', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Full name'}),
            'age': forms.NumberInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Age in years', 'min': 0}),
            'gender': forms.Select(attrs={'class': INPUT_CLASS}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Mobile number'}),
            'address': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 2, 'placeholder': 'Address'}),
        }

    def clean_address(self):
        raw = self.cleaned_data["address"]
        if "," in raw:
            raw = raw.split(",")[-1]
        return raw.strip().title()


class PatientAssignmentForm(forms.Form):
    """Which doctor the receptionist is registering this patient under."""

    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.none(),
        label="Consulting Doctor",
        empty_label=None,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        doctors = Doctor.objects.doctors().order_by('first_name', 'doctor_id')
        self.fields['doctor'].queryset = doctors
        self.fields['doctor'].label_from_instance = (
            lambda d: f"{d.display_name} — {d.doctor_id}"
                      + (f" · {d.specialization}" if d.specialization else "")
        )
        if doctors.count() == 1:
            self.fields['doctor'].initial = doctors.first()


# ---------------------------------------------------------------------------
# Additional Patient Record (research / registry)
# ---------------------------------------------------------------------------

TEXT_ATTRS = {'class': 'form-input'}
DATE_ATTRS = {'class': 'form-input', 'type': 'date'}
SELECT_ATTRS = {'class': 'form-input'}
CHECK_ATTRS = {'class': 'research-checkbox'}


class ClinicalResearchDataForm(forms.ModelForm):
    class Meta:
        model = ClinicalResearchData
        exclude = ['patient', 'created_at', 'updated_at']
        widgets = {
            'education_level': forms.Select(attrs=SELECT_ATTRS),
            'monthly_income': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'e.g. 15,000 BDT'}),
            'employment_status': forms.Select(attrs=SELECT_ATTRS),

            'diagnosis': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Primary renal disease / cause of failure (ERA-PRD coding)'}),
            'comorbid_diabetes': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'comorbid_hypertension': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'comorbid_heart_failure': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'comorbid_ischemic_heart_disease': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'comorbid_peripheral_artery_disease': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'comorbid_stroke': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'smoking_status': forms.Select(attrs=SELECT_ATTRS),
            # BMI is auto-calculated (client-side JS on the form, with a
            # server-side fallback in ClinicalResearchData.save()) from weight &
            # height, so the field is read-only and just displays the value.
            'bmi': forms.TextInput(attrs={
                **TEXT_ATTRS,
                'placeholder': 'Auto-calculated',
                'readonly': 'readonly',
                'id': 'id_bmi',
            }),
            'weight': forms.NumberInput(attrs={
                **TEXT_ATTRS,
                'placeholder': 'Weight (kg)',
                'id': 'id_weight',
                'step': '0.1',
                'min': '0',
            }),
            'height': forms.NumberInput(attrs={
                **TEXT_ATTRS,
                'placeholder': 'Height (cm)',
                'id': 'id_height',
                'step': '0.1',
                'min': '0',
            }),

            'serum_creatinine': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Serum creatinine'}),
            'cystatin_c': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Cystatin C'}),
            'egfr': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'eGFR'}),
            'uacr': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'uACR'}),
            'protein_levels': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Protein levels'}),
            'hemoglobin': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Hemoglobin'}),
            'ferritin': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Ferritin'}),
            'calcium': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Calcium'}),
            'phosphorus': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Phosphorus'}),
            'pth': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'PTH'}),
            'potassium': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Potassium'}),
            'bicarbonate': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Bicarbonate'}),
            'serum_albumin': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Serum albumin'}),
            'crp': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'CRP'}),
            'total_cholesterol': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Total cholesterol'}),
            'hba1c': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'HbA1c'}),

            'krt_modality': forms.Select(attrs=SELECT_ATTRS),
            'krt_initiation_date': forms.DateInput(attrs=DATE_ATTRS),
            'modality_change_dates': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'Dates of modality changes'}),
            'transplant_date': forms.DateInput(attrs=DATE_ATTRS),
            'dialysis_duration': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'e.g. 4 hours/session'}),
            'dialysis_frequency': forms.TextInput(attrs={**TEXT_ATTRS, 'placeholder': 'e.g. 3x/week'}),
            'vascular_access_type': forms.Select(attrs=SELECT_ATTRS),

            'med_esa': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_iron': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_phosphate_binders': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_vitamin_d': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_calcimimetics': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_ace_arb': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_diuretics': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_statins': forms.CheckboxInput(attrs=CHECK_ATTRS),
            'med_immunosuppressives': forms.CheckboxInput(attrs=CHECK_ATTRS),
        }


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

class AppointmentForm(forms.Form):
    """Place an existing patient into a doctor's queue for a given day."""

    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.none(),
        label="Doctor",
        empty_label=None,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    note = forms.CharField(
        required=False,
        max_length=200,
        label="Note (optional)",
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. Follow-up, report review'}),
    )

    def __init__(self, *args, **kwargs):
        initial_doctor = kwargs.pop('initial_doctor', None)
        super().__init__(*args, **kwargs)
        doctors = Doctor.objects.doctors().order_by('first_name', 'doctor_id')
        self.fields['doctor'].queryset = doctors
        self.fields['doctor'].label_from_instance = (
            lambda d: f"{d.display_name} — {d.doctor_id}"
        )
        if initial_doctor is not None:
            self.fields['doctor'].initial = initial_doctor
        elif doctors.count() == 1:
            self.fields['doctor'].initial = doctors.first()


# ---------------------------------------------------------------------------
# Admin panel: account management
# ---------------------------------------------------------------------------

def clean_new_login_id(raw, instance=None):
    """Validate a login ID for a brand new (or renamed) account."""
    login_id = normalize_login_id(raw or "")
    if not LOGIN_ID_RE.match(login_id):
        raise forms.ValidationError(
            "Use 3-32 letters, digits, dots, dashes or underscores."
        )
    clash = Doctor.objects.filter(doctor_id__iexact=login_id)
    if instance is not None and instance.pk:
        clash = clash.exclude(pk=instance.pk)
    if clash.exists():
        raise forms.ValidationError("An account with this ID already exists.")
    return login_id


class ManagedAccountForm(forms.ModelForm):
    """Create and edit accounts from the in-app admin panel.

    The role is normally implied by the ID (HF#### / RE####); it only has to be
    chosen explicitly when the ID follows neither clinic format, which is how
    administrator accounts are made.
    """

    password1 = forms.CharField(
        label="Password", required=False,
        widget=forms.PasswordInput(attrs={
            "class": INPUT_CLASS, "autocomplete": "new-password",
            "placeholder": "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"}),
    )
    password2 = forms.CharField(
        label="Confirm password", required=False,
        widget=forms.PasswordInput(attrs={
            "class": INPUT_CLASS, "autocomplete": "new-password",
            "placeholder": "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"}),
    )

    class Meta:
        model = Doctor
        fields = ["doctor_id", "role", "first_name", "last_name",
                  "email", "phone", "specialization", "is_active"]
        widgets = {
            "doctor_id": forms.TextInput(attrs={
                "class": INPUT_CLASS, "placeholder": "HF1234, RE0001 or admin-RX",
                "autocapitalize": "off", "spellcheck": "false"}),
            "role": forms.Select(attrs={"class": INPUT_CLASS}),
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "name@example.com"}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Contact number"}),
            "specialization": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "e.g. Nephrologist"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.creating = self.instance.pk is None
        self.fields["role"].choices = ROLE_CHOICES
        self.fields["is_active"].widget.attrs.update({"class": "research-checkbox"})
        if self.creating:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].help_text = "Leave blank to keep the current password."

    def clean_doctor_id(self):
        return clean_new_login_id(self.cleaned_data.get("doctor_id"), self.instance)

    def clean(self):
        cleaned = super().clean()
        login_id = cleaned.get("doctor_id")
        derived = role_for_user_id(login_id) if login_id else None
        if derived:
            # An HF/RE ID is authoritative; the model enforces this on save too.
            cleaned["role"] = derived
        elif login_id and not cleaned.get("role"):
            cleaned["role"] = ROLE_ADMIN

        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "The two passwords do not match.")
            elif len(p1) < 4:
                self.add_error("password1", "Use at least 4 characters.")
        return cleaned

    def save(self, commit=True):
        account = super().save(commit=False)
        account.role = self.cleaned_data.get("role") or account.role
        if not account.is_doctor:
            account.specialization = ""
        password = self.cleaned_data.get("password1")
        if password:
            account.set_password(password)
        # Administrators also get Django-admin access; clinic roles do not.
        account.is_staff = account.is_admin
        account.is_superuser = account.is_admin
        if commit:
            account.save()
        return account


class AccountPasswordForm(forms.Form):
    """Admin panel: set a new password on another account."""

    password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        elif p1 and len(p1) < 4:
            self.add_error("password1", "Use at least 4 characters.")
        return cleaned
