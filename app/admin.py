from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from app.forms import AccountChangeForm, AccountCreationForm
from app.models import (
    Appointment,
    ClinicalResearchData,
    Doctor,
    Examination,
    Medicine,
    MedicineMaster,
    Patient,
    PatientCall,
    Prescription,
    Problem,
    Report,
    ReportImage,
)


@admin.register(Doctor)
class AccountAdmin(UserAdmin):
    """Accounts are created here (or via `manage.py createaccount`) - there is
    no public registration. The role follows the login ID prefix: HF#### is a
    doctor, RE#### is a receptionist."""

    form = AccountChangeForm
    add_form = AccountCreationForm
    ordering = ('doctor_id',)
    list_display = ('doctor_id', 'role', 'first_name', 'last_name', 'specialization', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('doctor_id', 'first_name', 'last_name', 'email')

    fieldsets = (
        (None, {'fields': ('doctor_id', 'password', 'role')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone',
                                      'specialization', 'bio', 'profile_picture')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('doctor_id', 'password1', 'password2', 'first_name', 'last_name'),
            'description': 'Use HF#### for a doctor or RE#### for a receptionist.',
        }),
    )


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'age', 'gender', 'phone', 'doctor', 'registered_by', 'created_at')
    list_filter = ('gender', 'doctor')
    search_fields = ('name', 'phone', 'address')


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('date', 'serial', 'patient', 'doctor', 'status', 'created_by')
    list_filter = ('date', 'status', 'doctor')
    search_fields = ('patient__name',)


@admin.register(PatientCall)
class PatientCallAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'created_at', 'acknowledged', 'acknowledged_by')
    list_filter = ('acknowledged', 'doctor')


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'created_at')
    search_fields = ('patient__name',)


admin.site.register(Report)
admin.site.register(Problem)
admin.site.register(Examination)
admin.site.register(Medicine)
admin.site.register(ReportImage)
admin.site.register(MedicineMaster)
admin.site.register(ClinicalResearchData)

admin.site.site_header = "MultiRx Administration"
admin.site.site_title = "MultiRx Admin"
