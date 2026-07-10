from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Doctor
from .models import Patient
from .models import ClinicalResearchData




class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['name', 'age', 'address', 'gender']

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter patient name'
            }),
            'age': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter age'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Enter address'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-green-500'
            }),
        }

    def clean_address(self):
        raw = self.cleaned_data["address"]
        if "," in raw:
            raw = raw.split(",")[-1]
        normalised = raw.strip().title()
        return normalised


# forms.py
class DoctorRegistrationForm(UserCreationForm):
    specialization = forms.CharField(max_length=100, label="Specialization")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = Doctor
        fields = ['doctor_id', 'specialization', 'password1', 'password2']

    def clean_doctor_id(self):
        doctor_id = self.cleaned_data['doctor_id']
        if not (doctor_id.startswith("HF") and len(doctor_id) == 6):
            raise forms.ValidationError("You can't register. This is a private website.")
        
        if Doctor.objects.filter(doctor_id=doctor_id).exists():
            raise forms.ValidationError("This Doctor ID is already registered.")
            
        return doctor_id

from django import forms
from django.contrib.auth import get_user_model

class DoctorLoginForm(forms.Form):
    doctor_id = forms.CharField(
        max_length=6,
        label="Doctor ID",
        widget=forms.TextInput(attrs={
            'placeholder': 'HF1234',
            'autocomplete': 'username',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none input-field text-gray-700 placeholder-gray-400'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none input-field text-gray-700 placeholder-gray-400'
        }),
        label="Password"
    )

    def clean(self):
        cleaned_data = super().clean()
        doctor_id = cleaned_data.get('doctor_id')
        password = cleaned_data.get('password')
        
        if doctor_id and password:
            # Check if doctor_id starts with HF and is 6 characters
            if not (doctor_id.startswith("HF") and len(doctor_id) == 6):
                self.add_error('doctor_id', "Invalid Doctor ID format. Must start with HF and be 6 characters.")
            
            # Authentication check is now handled in the view
        return cleaned_data
    
    
class DoctorProfileUpdateForm(forms.ModelForm):

    class Meta:
        model = Doctor
        fields = ['profile_picture', 'first_name', 'last_name', 'email', 'bio', 'specialization']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_picture'].widget.attrs.update({
            'accept': 'image/*',
            'class': 'hidden'
        })
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        
        # Handle new profile picture
        if 'profile_picture' in self.changed_data:
            # Delete old picture if exists
            if instance.profile_picture:
                instance.profile_picture.delete()
            
        if commit:
            instance.save()
        
        return instance
    
from django import forms
from .models import Doctor

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
            if picture.content_type not in valid_types:
                raise forms.ValidationError("Only JPEG, PNG or GIF images are allowed")
        
        return picture


TEXT_ATTRS = {'class': 'form-input'}
DATE_ATTRS = {'class': 'form-input', 'type': 'date'}
SELECT_ATTRS = {'class': 'form-input'}
CHECK_ATTRS = {'class': 'research-checkbox'}


class ClinicalResearchDataForm(forms.ModelForm):
    class Meta:
        model = ClinicalResearchData
        exclude = ['prescription', 'created_at', 'updated_at']
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
            # BMI is auto-calculated (client-side JS in research_data.html, with a
            # server-side fallback in ClinicalResearchData.save()) from weight & height,
            # so the field is read-only and just displays the computed value.
            'bmi': forms.TextInput(attrs={
                **TEXT_ATTRS,
                'placeholder': 'Auto-calculated from weight & height',
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