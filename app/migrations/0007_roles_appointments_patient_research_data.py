"""Two-role accounts (Doctor / Receptionist), the appointment queue, and the
move of the "Additional Patient Record" from Prescription to Patient.

The Additional Patient Record is now filled in by the receptionist when the
patient is registered - before any prescription exists - so it hangs off the
Patient instead of a single Prescription.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def backfill_roles(apps, schema_editor):
    """Derive each existing account's role from its login ID prefix."""
    Doctor = apps.get_model('app', 'Doctor')
    for user in Doctor.objects.all():
        uid = (user.doctor_id or '').strip().upper()
        user.doctor_id = uid
        user.role = 'receptionist' if uid.startswith('RE') else 'doctor'
        user.save(update_fields=['doctor_id', 'role'])


def backfill_prescription_doctor(apps, schema_editor):
    """Existing prescriptions belong to the doctor their patient is under."""
    Prescription = apps.get_model('app', 'Prescription')
    for prescription in Prescription.objects.select_related('patient').all():
        prescription.doctor_id = prescription.patient.doctor_id
        prescription.save(update_fields=['doctor'])


def backfill_registered_by(apps, schema_editor):
    """Records that predate the receptionist role were entered by the doctor."""
    Patient = apps.get_model('app', 'Patient')
    Patient.objects.filter(registered_by__isnull=True).update(
        registered_by=models.F('doctor')
    )


def move_research_data_to_patient(apps, schema_editor):
    """Re-point each Additional Patient Record at its patient.

    A patient could previously have one record per prescription; keep the most
    recently updated one and drop the rest, since the patient now has exactly
    one such record.
    """
    ClinicalResearchData = apps.get_model('app', 'ClinicalResearchData')

    kept_by_patient = {}
    for record in (ClinicalResearchData.objects
                   .select_related('prescription')
                   .order_by('-updated_at', '-id')):
        if record.prescription_id is None:
            record.delete()
            continue
        patient_id = record.prescription.patient_id
        if patient_id in kept_by_patient:
            record.delete()
            continue
        kept_by_patient[patient_id] = record.id
        record.patient_id = patient_id
        record.save(update_fields=['patient'])

    # Anything still unlinked cannot be attached to a patient.
    ClinicalResearchData.objects.filter(patient__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_medicinemaster'),
    ]

    operations = [
        # --- Accounts ------------------------------------------------------
        migrations.AddField(
            model_name='doctor',
            name='role',
            field=models.CharField(
                choices=[('doctor', 'Doctor'), ('receptionist', 'Receptionist')],
                default='doctor', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='doctor',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='doctor',
            name='doctor_id',
            field=models.CharField(max_length=6, unique=True, verbose_name='Login ID'),
        ),
        migrations.AlterField(
            model_name='doctor',
            name='specialization',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(backfill_roles, migrations.RunPython.noop),

        # --- Patients ------------------------------------------------------
        migrations.AddField(
            model_name='patient',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='patient',
            name='registered_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='registered_patients',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='patient',
            name='doctor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='patients',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_registered_by, migrations.RunPython.noop),

        # --- Prescriptions --------------------------------------------------
        migrations.AddField(
            model_name='prescription',
            name='doctor',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='prescriptions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_prescription_doctor, migrations.RunPython.noop),

        # --- Additional Patient Record: Prescription -> Patient --------------
        migrations.AddField(
            model_name='clinicalresearchdata',
            name='patient',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='research_data_migrating',
                to='app.patient',
            ),
        ),
        migrations.RunPython(move_research_data_to_patient, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='clinicalresearchdata',
            name='prescription',
        ),
        migrations.AlterField(
            model_name='clinicalresearchdata',
            name='patient',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='research_data',
                to='app.patient',
            ),
        ),

        # --- Appointment queue ----------------------------------------------
        migrations.CreateModel(
            name='Appointment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('serial', models.PositiveIntegerField()),
                ('status', models.CharField(
                    choices=[
                        ('waiting', 'Waiting'),
                        ('in_consultation', 'In Consultation'),
                        ('completed', 'Completed'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='waiting', max_length=20,
                )),
                ('note', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('called_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_appointments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='doctor_appointments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appointments',
                    to='app.patient',
                )),
                ('prescription', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='appointments',
                    to='app.prescription',
                )),
            ],
            options={
                'ordering': ['date', 'serial'],
                'unique_together': {('doctor', 'date', 'serial')},
            },
        ),
        migrations.CreateModel(
            name='PatientCall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='acknowledged_calls',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='patient_calls',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('finished_appointment', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='calls',
                    to='app.appointment',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
