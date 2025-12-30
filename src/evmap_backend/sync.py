import logging
from itertools import batched
from typing import Iterable, List, Tuple

from django.db import transaction
from django.forms import model_to_dict
from tqdm import tqdm

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector
from evmap_backend.helpers.database import distinct_on
from evmap_backend.realtime.models import RealtimeStatus


def _sync_sites_batch(
    data_source: str,
    batch: Tuple[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]], ...],
    site_ids_to_delete: set,
    progress_bar: tqdm,
) -> int:
    """
    Sync a batch of sites using bulk operations.
    Returns the number of sites created in this batch.
    """
    sites_created = 0

    # Extract all unique site id_from_source values in this batch
    batch_site_ids = {site.id_from_source for site, _ in batch}

    # Fetch existing sites for this batch
    existing_sites = {
        s.id_from_source: s
        for s in ChargingSite.objects.filter(
            data_source=data_source, id_from_source__in=batch_site_ids
        )
    }

    # Separate sites into create and update lists
    sites_to_create = []
    sites_to_update = []
    site_mapping = {}  # Map id_from_source to site object

    for site, _ in batch:
        if site.id_from_source in existing_sites:
            # Update existing site
            existing_site = existing_sites[site.id_from_source]
            site_dict = model_to_dict(
                site, exclude=["data_source", "id_from_source", "id"]
            )
            for field, value in site_dict.items():
                setattr(existing_site, field, value)
            sites_to_update.append(existing_site)
            site_mapping[site.id_from_source] = existing_site

            # Check for duplicates globally using site_ids_to_delete
            if existing_site.id not in site_ids_to_delete:
                logging.warning(
                    f"ID {site.id_from_source} seems to appear more than once in input data!"
                )
            site_ids_to_delete.discard(existing_site.id)
        else:
            # Create new site
            site.data_source = data_source
            sites_to_create.append(site)
            site_mapping[site.id_from_source] = site
            sites_created += 1

    # Bulk create new sites
    if sites_to_create:
        ChargingSite.objects.bulk_create(sites_to_create)

    # Bulk update existing sites
    if sites_to_update:
        update_fields = [
            field.name
            for field in ChargingSite._meta.get_fields()
            if field.name not in ["id", "data_source", "id_from_source"]
            and hasattr(field, "attname")
        ]
        ChargingSite.objects.bulk_update(sites_to_update, update_fields)

    # Process all chargepoints and connectors in this batch together
    _sync_chargepoints_and_connectors_batch(batch, site_mapping, progress_bar)

    return sites_created


def _sync_chargepoints_and_connectors_batch(
    batch: Tuple[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]], ...],
    site_mapping: dict,
    progress_bar: tqdm,
):
    """
    Sync all chargepoints and connectors for all sites in the batch using bulk operations.
    This is more efficient than processing each site individually since sites typically have few chargepoints.
    """
    # Collect all site IDs in this batch
    batch_site_ids = [site_mapping[site.id_from_source].id for site, _ in batch]

    # Fetch all existing chargepoints for all sites in the batch in one query
    all_existing_chargepoints = Chargepoint.objects.filter(site_id__in=batch_site_ids)

    # Group by (site_id, id_from_source) for quick lookup
    existing_chargepoints_map = {
        (cp.site_id, cp.id_from_source): cp for cp in all_existing_chargepoints
    }

    # Track which chargepoint IDs should be deleted
    chargepoint_ids_to_delete = set(cp.id for cp in all_existing_chargepoints)

    # Collect all chargepoints to create/update across all sites
    chargepoints_to_create = []
    chargepoints_to_update = []
    chargepoint_mapping = {}  # Map (site_id, id_from_source) to chargepoint object
    created_chargepoint_keys = set()

    # Collect all connector data for later processing
    all_connectors_data = []  # List of (chargepoint_key, connectors_data, is_new)

    for site_data, chargepoints_data in batch:
        site = site_mapping[site_data.id_from_source]

        for chargepoint, connectors_data in chargepoints_data:
            cp_key = (site.id, chargepoint.id_from_source)

            if cp_key in existing_chargepoints_map:
                # Update existing chargepoint
                existing_cp = existing_chargepoints_map[cp_key]
                cp_dict = model_to_dict(
                    chargepoint, exclude=["site", "id_from_source", "id"]
                )
                for field, value in cp_dict.items():
                    setattr(existing_cp, field, value)
                chargepoints_to_update.append(existing_cp)
                chargepoint_mapping[cp_key] = existing_cp

                # Check for duplicates globally
                if existing_cp.id not in chargepoint_ids_to_delete:
                    logging.warning(
                        f"ID {chargepoint.id_from_source} seems to appear more than once in input data!"
                    )
                chargepoint_ids_to_delete.discard(existing_cp.id)
                all_connectors_data.append((cp_key, connectors_data, False))
            else:
                # Create new chargepoint
                chargepoint.site = site
                chargepoints_to_create.append(chargepoint)
                chargepoint_mapping[cp_key] = chargepoint
                created_chargepoint_keys.add(cp_key)
                all_connectors_data.append((cp_key, connectors_data, True))

    # Bulk create new chargepoints
    if chargepoints_to_create:
        Chargepoint.objects.bulk_create(chargepoints_to_create)

    # Bulk update existing chargepoints
    if chargepoints_to_update:
        update_fields = [
            field.name
            for field in Chargepoint._meta.get_fields()
            if field.name not in ["id", "site", "id_from_source"]
            and hasattr(field, "attname")
        ]
        Chargepoint.objects.bulk_update(chargepoints_to_update, update_fields)

    # Now process all connectors across all chargepoints in the batch
    _sync_connectors_batch(all_connectors_data, chargepoint_mapping, batch_site_ids)

    # Delete missing chargepoints in one query
    if chargepoint_ids_to_delete:
        Chargepoint.objects.filter(id__in=chargepoint_ids_to_delete).delete()

    # Update progress for all sites in the batch
    for _ in batch:
        progress_bar.update(1)


def _sync_connectors_batch(
    all_connectors_data: List[Tuple[Tuple[int, str], List[Connector], bool]],
    chargepoint_mapping: dict,
    batch_site_ids: List[int],
):
    """
    Sync all connectors for all chargepoints in the batch using bulk operations.
    """
    # Fetch all existing connectors for all chargepoints in the batch in one query
    all_existing_connectors = Connector.objects.filter(
        chargepoint__site_id__in=batch_site_ids
    )

    # Group by (chargepoint_id, id_from_source) for quick lookup
    existing_connectors_map = {
        (conn.chargepoint_id, conn.id_from_source): conn
        for conn in all_existing_connectors
    }

    # Track which connector IDs should be deleted
    connector_ids_to_delete = set(conn.id for conn in all_existing_connectors)

    # For the fallback case, we need to prefetch existing connectors by chargepoint
    # Build a map of chargepoint_id -> list of connector dicts
    existing_connectors_by_cp = {}
    for conn in all_existing_connectors:
        if conn.chargepoint_id not in existing_connectors_by_cp:
            existing_connectors_by_cp[conn.chargepoint_id] = []
        existing_connectors_by_cp[conn.chargepoint_id].append(
            model_to_dict(conn, exclude=["chargepoint", "id"])
        )

    # Separate connectors with IDs from those without
    connectors_with_ids = []
    connectors_without_ids = []

    for cp_key, connectors_data, is_new_chargepoint in all_connectors_data:
        chargepoint = chargepoint_mapping[cp_key]

        if all(conn.id_from_source is not None for conn in connectors_data):
            connectors_with_ids.append((chargepoint, connectors_data))
        else:
            connectors_without_ids.append(
                (chargepoint, connectors_data, is_new_chargepoint)
            )

    # Process connectors with IDs using bulk operations
    connectors_to_create = []
    connectors_to_update = []

    for chargepoint, connectors_data in connectors_with_ids:
        for connector in connectors_data:
            conn_key = (chargepoint.id, connector.id_from_source)

            if conn_key in existing_connectors_map:
                # Update existing connector
                existing_conn = existing_connectors_map[conn_key]
                conn_dict = model_to_dict(
                    connector, exclude=["chargepoint", "id_from_source", "id"]
                )
                for field, value in conn_dict.items():
                    setattr(existing_conn, field, value)
                connectors_to_update.append(existing_conn)
                connector_ids_to_delete.discard(existing_conn.id)
            else:
                # Create new connector
                connector.chargepoint = chargepoint
                connectors_to_create.append(connector)

    # Process connectors without IDs using the fallback logic
    for chargepoint, connectors_data, is_new_chargepoint in connectors_without_ids:
        if not is_new_chargepoint:
            # Check if the existing connectors match the updated ones
            new_connectors = [
                model_to_dict(connector, exclude=["chargepoint", "id"])
                for connector in connectors_data
            ]
            # Use prefetched data instead of querying
            existing_connectors = existing_connectors_by_cp.get(chargepoint.id, [])
            if len(new_connectors) == len(existing_connectors) and all(
                conn in existing_connectors for conn in new_connectors
            ):
                # No changes needed, remove these connectors from deletion list
                for conn_id in [
                    c.id
                    for c in all_existing_connectors
                    if c.chargepoint_id == chargepoint.id
                ]:
                    connector_ids_to_delete.discard(conn_id)
                continue

        # Add new connectors to create list
        for connector in connectors_data:
            connector.chargepoint = chargepoint
            connectors_to_create.append(connector)

    # Bulk create new connectors
    if connectors_to_create:
        Connector.objects.bulk_create(connectors_to_create)

    # Bulk update existing connectors
    if connectors_to_update:
        update_fields = [
            field.name
            for field in Connector._meta.get_fields()
            if field.name not in ["id", "chargepoint", "id_from_source"]
            and hasattr(field, "attname")
        ]
        Connector.objects.bulk_update(connectors_to_update, update_fields)

    # Delete missing connectors in one query
    if connector_ids_to_delete:
        Connector.objects.filter(id__in=connector_ids_to_delete).delete()


def sync_chargers(
    data_source: str,
    sites: Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]],
    delete_missing: bool = True,
):
    """
    Sync charging sites from a data source using bulk operations.
    Processes sites in batches of 100 for efficiency.
    """
    total_sites_created = 0
    total_sites_deleted = 0

    with transaction.atomic():
        # Get all site IDs that should be deleted (will be reduced as we process batches)
        site_ids_to_delete = set(
            ChargingSite.objects.filter(data_source=data_source).values_list(
                "id", flat=True
            )
        )

        # Process sites in batches
        batch_size = 100

        # Create a progress bar for all sites
        # We'll update it as we process each site within batches
        with tqdm(desc="Syncing sites") as progress_bar:
            for batch in batched(sites, batch_size):
                sites_created = _sync_sites_batch(
                    data_source, batch, site_ids_to_delete, progress_bar
                )
                total_sites_created += sites_created

        # Delete all remaining sites that weren't in the input
        if site_ids_to_delete and delete_missing:
            ChargingSite.objects.filter(id__in=site_ids_to_delete).delete()
            total_sites_deleted = len(site_ids_to_delete)

        print(
            f"{total_sites_created} sites created, {total_sites_deleted} sites deleted"
        )


def sync_statuses(
    realtime_data_source: str,
    chargepoint_data_source: str,
    statuses: Iterable[Tuple[str, RealtimeStatus]],
):
    """
    Sync charger statuses using bulk operations.
    Processes statuses in batches for efficiency.
    """
    total_statuses_created = 0
    batch_size = 100

    with transaction.atomic():
        for batch in tqdm(batched(statuses, batch_size), desc="Syncing statuses"):
            statuses_created = _sync_statuses_batch(
                realtime_data_source, chargepoint_data_source, batch
            )
            total_statuses_created += statuses_created

        print(f"Created {total_statuses_created} statuses")


def _sync_statuses_batch(
    realtime_data_source: str,
    chargepoint_data_source: str,
    batch: Tuple[Tuple[str, RealtimeStatus], ...],
) -> int:
    """
    Sync a batch of statuses using bulk operations.
    Returns the number of statuses created in this batch.
    """
    # Fetch all chargepoints for this batch in one query
    chargepoints = Chargepoint.objects.select_related("site").filter(
        site__data_source=chargepoint_data_source,
        site__id_from_source__in=[site_id for site_id, _ in batch],
    )

    # Build a mapping of (site_id_from_source, chargepoint_id_from_source) -> chargepoint
    chargepoint_map = {
        (cp.site.id_from_source, cp.id_from_source): cp for cp in chargepoints
    }

    # Fetch the latest status for each chargepoint
    latest_statuses_qs = distinct_on(
        RealtimeStatus.objects.filter(
            data_source=realtime_data_source,
            chargepoint__in=chargepoint_map.values(),
        ),
        distinct_fields=["chargepoint_id"],
        order_field="timestamp",
    )

    # Build a mapping of chargepoint_id -> latest status
    latest_status_map = {status.chargepoint_id: status for status in latest_statuses_qs}

    # Collect statuses to create
    statuses_to_create = []

    for site_id, status in batch:
        cp_key = (site_id, status.chargepoint.id_from_source)
        chargepoint = chargepoint_map.get(cp_key)

        if chargepoint is None:
            logging.warning(
                f"Chargepoint {site_id}/{status.chargepoint.id_from_source} not found, ignoring status update"
            )
            continue

        latest_status = latest_status_map.get(chargepoint.id)

        if latest_status is None or status.timestamp > latest_status.timestamp:
            status.chargepoint = chargepoint
            status.data_source = realtime_data_source
            statuses_to_create.append(status)

    # Bulk create new statuses
    if statuses_to_create:
        RealtimeStatus.objects.bulk_create(statuses_to_create)

    return len(statuses_to_create)
