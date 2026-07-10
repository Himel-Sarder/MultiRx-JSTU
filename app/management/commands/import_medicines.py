import csv
from django.core.management.base import BaseCommand
from app.models import MedicineMaster


class Command(BaseCommand):
    help = "Import the master medicine list from a CSV file (columns: 'Medicine Name', 'Uses')."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            nargs="?",
            default="data/Medicines.csv",
            help="Path to the medicines CSV file (default: data/Medicines.csv)",
        )

    def handle(self, *args, **opts):
        path = opts["csv_file"]
        created, updated, skipped = 0, 0, 0

        # utf-8-sig gracefully strips a BOM if the CSV has one.
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw_name = (row.get("Medicine Name") or "").strip()
                if not raw_name:
                    skipped += 1
                    continue

                name = raw_name.title()
                uses = (row.get("Uses") or "").strip()

                obj, was_created = MedicineMaster.objects.update_or_create(
                    name=name,
                    defaults={"uses_raw": uses},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import complete. Created: {created}, Updated: {updated}, Skipped: {skipped}"
        ))
