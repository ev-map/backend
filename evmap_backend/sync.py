from typing import Iterable, List, Tuple

from django.db import transaction
from django.forms import model_to_dict

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector


def sync_chargers(
    data_source: str,
    sites: Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]],
):
    sites_created = 0
    with transaction.atomic():
        site_ids_to_delete = set(
            ChargingSite.objects.filter(data_source=data_source).values_list(
                "id", flat=True
            )
        )
        for site, chargepoints in sites:
            site, created = ChargingSite.objects.update_or_create(
                data_source=data_source,
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
            for chargepoint, connectors in chargepoints:
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
                    new_connectors = [
                        model_to_dict(connector, exclude=["chargepoint", "id"])
                        for connector in connectors
                    ]
                    existing_connectors = [
                        model_to_dict(conn, exclude=["chargepoint", "id"])
                        for conn in chargepoint.connectors.all()
                    ]
                    if len(new_connectors) == len(existing_connectors) and all(
                        conn in existing_connectors for conn in new_connectors
                    ):
                        continue

                # delete all connectors and save the new ones to the DB
                chargepoint.connectors.all().delete()

                for connector in connectors:
                    connector.chargepoint = chargepoint
                    connector.save()

            # delete missing chargepoints
            Chargepoint.objects.filter(id__in=chargepoint_ids_to_delete).delete()

        # delete missing sites
        ChargingSite.objects.filter(id__in=site_ids_to_delete).delete()
        sites_deleted = len(site_ids_to_delete)

        print(f"{sites_created} sites created, {sites_deleted} sites deleted")
