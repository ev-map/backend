import io

import openpyxl
import requests
from django.core.management import BaseCommand
from django.db import models
from django.db.models import Q

from evmap_backend.chargers.fields import normalize_evseid, validate_evse_operator_id
from evmap_backend.chargers.models import Network

BDEW_DOWNLOAD_URL = (
    "https://bdew-codes.de/Codenumbers/EMobilityId/DownloadActiveEVSECodes"
)


class Command(BaseCommand):
    help = "Load EVSE operator names for Germany from the Excel sheet provided by BDEW and update networks without a name."

    def handle(self, *args, **options):
        self.stdout.write("Downloading BDEW EVSE Operator IDs...")
        response = requests.get(BDEW_DOWNLOAD_URL, timeout=30)
        response.raise_for_status()

        wb = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            self.stdout.write(self.style.ERROR("Excel sheet is empty."))
            return

        header = [str(cell or "").strip().lower() for cell in rows[0]]
        if header[:2] != ["code", "company"]:
            self.stdout.write(
                self.style.ERROR(
                    f"Unexpected columns: {header}. Expected ['code', 'company']."
                )
            )
            return

        # Build mapping: normalized operator ID -> company name
        bdew_names = {}
        for row in rows[1:]:
            raw_id = str(row[0] or "").strip()
            company_name = str(row[1] or "").strip()
            if not raw_id or not company_name:
                continue
            normalized_id = normalize_evseid(raw_id)
            validate_evse_operator_id(normalized_id)
            bdew_names[normalized_id] = company_name

        self.stdout.write(f"Parsed {len(bdew_names)} operator entries from BDEW sheet.")

        # Update networks where name is blank or equals the evse_operator_id
        networks = Network.objects.filter(
            Q(name="") | Q(name=models.F("evse_operator_id"))
        ).exclude(evse_operator_id="")

        updated = 0
        for network in networks:
            new_name = bdew_names.get(network.evse_operator_id)
            if new_name:
                network.name = new_name
                network.save(update_fields=["name"])
                self.stdout.write(f"  Updated {network.evse_operator_id} -> {new_name}")
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated} network(s)."))
