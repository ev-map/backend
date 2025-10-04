from typing import Iterable

from django.db import transaction
from django.forms import model_to_dict

from evmap_backend.chargers.models import Chargepoint, ChargingSite
from evmap_backend.data_sources.datex2.parser import Datex2EnergyInfrastructureSite


def sync_chargers(sites_datex: Iterable[Datex2EnergyInfrastructureSite], source: str):
    sites_created = 0
    with transaction.atomic():
        site_ids_to_delete = set(
            ChargingSite.objects.filter(data_source=source).values_list("id", flat=True)
        )
        for site_datex in sites_datex:
            site = site_datex.convert(source)
            site, created = ChargingSite.objects.update_or_create(
                data_source=source,
                id_from_source=site.id_from_source,
                defaults=model_to_dict(
                    site, exclude=["data_source", "id_from_source", "id"]
                ),
            )
            if created:
                sites_created += 1
            else:
                site_ids_to_delete.remove(site.id)

            chargepoint_ids_to_delete = set(
                Chargepoint.objects.filter(site=site).values_list("id", flat=True)
            )
            for chargepoint_datex in site_datex.refill_points:
                chargepoint = chargepoint_datex.convert()
                chargepoint, created = Chargepoint.objects.update_or_create(
                    site=site,
                    id_from_source=chargepoint.id_from_source,
                    defaults=model_to_dict(
                        chargepoint, exclude=["site", "id_from_source", "id"]
                    ),
                )

                if not created:
                    chargepoint_ids_to_delete.remove(chargepoint.id)

                    # check if the existing connectors match the updated ones
                    connectors = [
                        model_to_dict(
                            connector.convert(), exclude=["chargepoint", "id"]
                        )
                        for connector in chargepoint_datex.connectors
                    ]
                    existing_connectors = [
                        model_to_dict(conn, exclude=["chargepoint", "id"])
                        for conn in chargepoint.connectors.all()
                    ]
                    if len(connectors) == len(existing_connectors) and all(
                        conn in existing_connectors for conn in connectors
                    ):
                        continue

                # delete all connectors and save the new ones to the DB
                chargepoint.connectors.all().delete()

                for connector_datex in chargepoint_datex.connectors:
                    connector = connector_datex.convert()
                    connector.chargepoint = chargepoint
                    connector.save()

            # delete missing chargepoints
            Chargepoint.objects.filter(id__in=chargepoint_ids_to_delete).delete()

        # delete missing sites
        ChargingSite.objects.filter(id__in=site_ids_to_delete).delete()
        sites_deleted = len(site_ids_to_delete)

        print(f"{sites_created} sites created, {sites_deleted} sites deleted")
