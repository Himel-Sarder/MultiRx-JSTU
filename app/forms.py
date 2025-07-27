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

    def clean_address(self):
        raw = self.cleaned_data["address"]
        if "," in raw:
            raw = raw.split(",")[-1]
        normalised = raw.strip().title()
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