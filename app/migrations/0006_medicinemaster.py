# Generated for MedicineMaster (CSV-backed medicine catalogue for autocomplete)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_clinicalresearchdata'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicineMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=255, unique=True)),
                ('uses_raw', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
    ]
