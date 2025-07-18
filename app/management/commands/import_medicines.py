import csv, re
from django.core.management.base import BaseCommand
from app.models import MedicineMaster

class Command(BaseCommand):
    help = "Import master medicine list from CSV"

    def add_arguments(self, parser):
        parser.add_argument("csv_file")

    def handle(self, *args, **opts):
        with open(opts["csv_file"], newline="", encoding="utf‑8") as fh:
            for row in csv.DictReader(fh):
                MedicineMaster.objects.update_or_create(
                    name=row["Medicine Name"].strip().title(),
                    defaults={"uses_raw": row["Uses"]},
                )
        self.stdout.write(self.style.SUCCESS("✅ Import complete"))
