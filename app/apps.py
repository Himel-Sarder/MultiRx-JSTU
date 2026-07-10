from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_auto_import_medicines, sender=self)


def _auto_import_medicines(sender, **kwargs):
    """
    After migrations run, automatically load data/Medicines.csv into
    MedicineMaster if the table is empty. This means the medicine-name
    autocomplete (which reads from MedicineMaster) works out of the box
    after deployment, without anyone needing to run the management
    command by hand.
    """
    import os
    from django.conf import settings

    try:
        from .models import MedicineMaster
    except Exception:
        return

    try:
        if MedicineMaster.objects.exists():
            return
    except Exception:
        # Table may not exist yet in some edge cases (e.g. during initial
        # migration of a fresh test DB) - just skip silently.
        return

    csv_path = os.path.join(settings.BASE_DIR, 'data', 'Medicines.csv')
    if not os.path.exists(csv_path):
        return

    from django.core.management import call_command
    try:
        call_command('import_medicines', csv_path)
    except Exception:
        # Never break app startup because of a bad/missing CSV.
        pass
