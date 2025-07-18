from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Doctor
from .models import Patient




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
        # ↓ NEW: normalise the address
    def clean_address(self):
        raw = self.cleaned_data["address"]

        # 1. If the user typed sub‑area + district (comma‑separated),
        #    keep only the LAST part (the district)
        if "," in raw:
            raw = raw.split(",")[-1]

        # 2. Trim whitespace and convert to Title‑case
        normalised = raw.strip().title()           # "  sherpur " -> "Sherpur"

        return normalised


class DoctorRegistrationForm(UserCreationForm):
    doctor_id = forms.CharField(max_length=6, label="Doctor ID")
    specialization = forms.CharField(max_length=100, label="Specialization")
    email = forms.EmailField(label="Email")

    class Meta:
        model = Doctor
        fields = ['doctor_id', 'specialization', 'username', 'first_name', 'email', 'password1', 'password2']

    def clean_doctor_id(self):
        doctor_id = self.cleaned_data['doctor_id']
        if not (doctor_id.startswith("HF") and len(doctor_id) == 6):
            raise forms.ValidationError("You can't register. This is a private website.")
        return doctor_id

class DoctorLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)




class DoctorProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['first_name', 'last_name', 'email', 'specialization', 'bio', 'profile_picture']
