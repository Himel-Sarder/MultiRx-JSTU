"""Administrator accounts.

Adds a third role and widens the login ID field, so an ID like `admin-RX` (which
does not follow the HF####/RE#### clinic formats) can sign in and land on the
admin panel instead of a doctor or reception console.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_roles_appointments_patient_research_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctor',
            name='doctor_id',
            field=models.CharField(max_length=32, unique=True, verbose_name='Login ID'),
        ),
        migrations.AlterField(
            model_name='doctor',
            name='role',
            field=models.CharField(
                choices=[
                    ('doctor', 'Doctor'),
                    ('receptionist', 'Receptionist'),
                    ('admin', 'Administrator'),
                ],
                default='doctor', max_length=20,
            ),
        ),
    ]
