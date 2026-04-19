import logging
from itertools import batched
from typing import Iterable, List, Tuple

import pgbulk
from django.db import transaction
from django.forms import model_to_dict
from tqdm import tqdm

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector
from evmap_backend.helpers.database import distinct_on
from evmap_backend.realtime.models import RealtimeStatus


def _get_update_fields(model, exclude_fields):
    """Get all updatable field names for a model, excluding specified fields."""
    return [
        field.name
        for field in model._meta.get_fields()
        if field.name not in exclude_fields and hasattr(field, "attname")
    ]


SITE_UPDATE_FIELDS = None
CP_UPDATE_FIELDS = None
CONN_UPDATE_FIELDS = None


def _get_cached_update_fields():
    """Lazily compute and cache the update field lists for each model."""
    global SITE_UPDATE_FIELDS, CP_UPDATE_FIELDS, CONN_UPDATE_FIELDS
    if SITE_UPDATE_FIELDS is None:
        SITE_UPDATE_FIELDS = _get_update_fields(
            ChargingSite, {"id", "data_source", "id_from_source", "location_mercator"}
        )
        CP_UPDATE_FIELDS = _get_update_fields(
            Chargepoint, {"id", "site", "id_from_source"}
        )
        CONN_UPDATE_FIELDS = _get_update_fields(
            Connector, {"id", "chargepoint", "id_from_source"}
        )
    return SITE_UPDATE_FIELDS, CP_UPDATE_FIELDS, CONN_UPDATE_FIELDS


def _sync_batch(
    data_source: str,
    batch: Tuple[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]], ...],
    seen_site_ids: set,
    existing_site_ids: set,
) -> int:
    """
    Sync a batch of sites with their chargepoints and connectors using pgbulk.upsert.
    Returns the number of sites created in this batch.
    """
    site_fields, cp_fields, conn_fields = _get_cached_update_fields()

    # Prepare sites
    for site_id, _ in batch:
        site_id.data_source = data_source

    # Upsert sites
    pgbulk.upsert(
        ChargingSite,
        [site for site, _ in batch],
        ["data_source", "id_from_source"],
        site_fields,
        ignore_unchanged=True,
    )

    # Fetch IDs of the inserted sites
    source_ids = [site.id_from_source for site, _ in batch]
    site_qs = ChargingSite.objects.filter(
        data_source=data_source, id_from_source__in=source_ids
    ).values_list("id_from_source", "id")
    site_map = dict(site_qs)
    batch_site_ids = site_map.values()
    seen_site_ids.update(batch_site_ids)
    sites_created = sum(1 for sid in batch_site_ids if sid not in existing_site_ids)

    # Collect and prepare chargepoints
    all_chargepoints = []
    cp_connectors = []  # parallel list of connector lists

    for site_data, chargepoints_data in batch:
        site_id = site_map[site_data.id_from_source]
        for cp, connectors in chargepoints_data:
            cp.site_id = site_id
            all_chargepoints.append(cp)
            cp_connectors.append(connectors)

    if all_chargepoints:
        # Upsert chargepoints
        pgbulk.upsert(
            Chargepoint,
            all_chargepoints,
            ["site", "id_from_source"],
            cp_fields,
            ignore_unchanged=True,
        )

        # Fetch ID mapping
        cp_qs = Chargepoint.objects.filter(site_id__in=batch_site_ids).values_list(
            "site_id", "id_from_source", "id"
        )
        cp_map = {
            (site_id, id_from_source): id for site_id, id_from_source, id in cp_qs
        }

        # Delete chargepoints not in input
        expected_keys = {(cp.site_id, cp.id_from_source) for cp in all_chargepoints}
        batch_cp_ids = [cp_map[k] for k in expected_keys if k in cp_map]
        Chargepoint.objects.filter(site_id__in=batch_site_ids).exclude(
            id__in=batch_cp_ids
        ).delete()

        # Process connectors
        _sync_connectors(
            all_chargepoints,
            cp_connectors,
            cp_map,
            batch_cp_ids,
            conn_fields,
        )
    else:
        # No chargepoints — delete all existing ones for these sites
        Chargepoint.objects.filter(site_id__in=batch_site_ids).delete()

    return sites_created


def _sync_connectors(
    original_cps: List[Chargepoint],
    cp_connectors: List[List[Connector]],
    cp_map: dict,
    batch_cp_ids: List[int],
    conn_update_fields: List[str],
):
    """
    Sync connectors for all chargepoints in the batch.

    Connectors that have an id_from_source are upserted via pgbulk.
    Connectors without an id_from_source use a fallback: if the set of
    connectors hasn't changed, existing rows are kept; otherwise they are
    replaced wholesale.
    """
    connectors_with_ids = []
    connectors_without_ids_data = []  # list of (resolved_cp, connectors)

    for original_cp, connectors in zip(original_cps, cp_connectors):
        resolved_cp_id = cp_map[(original_cp.site_id, original_cp.id_from_source)]

        if connectors and all(c.id_from_source is not None for c in connectors):
            for conn in connectors:
                conn.chargepoint_id = resolved_cp_id
            connectors_with_ids.extend(connectors)
        else:
            connectors_without_ids_data.append((resolved_cp_id, connectors))

    # Upsert connectors that have IDs
    upserted_connector_ids = set()
    if connectors_with_ids:
        pgbulk.upsert(
            Connector,
            connectors_with_ids,
            ["chargepoint", "id_from_source"],
            conn_update_fields,
            ignore_unchanged=True,
        )

        with_id_cp_ids = {con.chargepoint_id for con in connectors_with_ids}
        con_qs = Connector.objects.filter(
            chargepoint_id__in=with_id_cp_ids
        ).values_list("chargepoint_id", "id_from_source", "id")
        con_map = {
            (chargepoint_id, id_from_source): id
            for chargepoint_id, id_from_source, id in con_qs
        }

        # Delete connectors not in input
        expected_keys = {
            (con.chargepoint_id, con.id_from_source) for con in connectors_with_ids
        }
        upserted_connector_ids = {con_map[k] for k in expected_keys if k in con_map}

    # Handle connectors without IDs (fallback: compare and replace if changed)
    keep_connector_ids = set()
    connectors_to_create = []

    if connectors_without_ids_data:
        no_id_cp_ids = [cp_id for cp_id, _ in connectors_without_ids_data]
        existing_connectors = list(
            Connector.objects.filter(chargepoint_id__in=no_id_cp_ids)
        )
        existing_by_cp = {}
        for conn in existing_connectors:
            existing_by_cp.setdefault(conn.chargepoint_id, []).append(conn)

        for cp_id, new_connectors in connectors_without_ids_data:
            existing = existing_by_cp.get(cp_id, [])
            new_dicts = [
                model_to_dict(c, exclude=["chargepoint", "id"]) for c in new_connectors
            ]
            existing_dicts = [
                model_to_dict(c, exclude=["chargepoint", "id"]) for c in existing
            ]

            if len(new_dicts) == len(existing_dicts) and all(
                d in existing_dicts for d in new_dicts
            ):
                # No changes — keep existing connectors
                keep_connector_ids.update(c.id for c in existing)
            else:
                # Changes detected — create new (old ones will be deleted below)
                for conn in new_connectors:
                    conn.chargepoint_id = cp_id
                    connectors_to_create.append(conn)

    if connectors_to_create:
        created = Connector.objects.bulk_create(connectors_to_create)
        keep_connector_ids.update(c.id for c in created)

    # Delete connectors not accounted for
    all_valid_ids = upserted_connector_ids | keep_connector_ids
    delete_qs = Connector.objects.filter(chargepoint_id__in=batch_cp_ids)
    if all_valid_ids:
        delete_qs = delete_qs.exclude(id__in=all_valid_ids)
    delete_qs.delete()


def _deduplicate_sites(
    sites: Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]],
) -> Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]]:
    """
    Yield sites, skipping any whose id_from_source has already been seen.
    Logs a warning for each duplicate encountered.
    """
    seen_ids = set()
    for site, chargepoints in sites:
        if site.id_from_source in seen_ids:
            logging.warning(
                f"Duplicate site ID '{site.id_from_source}' — ignoring duplicate"
            )
            continue
        if site.location.y in [-90.0, 90.0]:
            logging.warning(
                f"Site '{site.id_from_source}' with invalid location {site.location} — ignoring"
            )
            continue
        seen_ids.add(site.id_from_source)
        yield site, chargepoints


def sync_chargers(
    data_source: str,
    sites: Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]],
    delete_missing: bool = True,
):
    """
    Sync charging sites from a data source using pgbulk upsert.
    Processes sites in batches of 1000 for efficiency.
    """
    with transaction.atomic():
        existing_site_ids = set(
            ChargingSite.objects.filter(data_source=data_source).values_list(
                "id", flat=True
            )
        )
        seen_site_ids = set()
        total_sites_created = 0

        batch_size = 1000
        with tqdm(desc="Syncing sites", disable=None) as progress_bar:
            for batch in batched(_deduplicate_sites(sites), batch_size):
                created = _sync_batch(
                    data_source, batch, seen_site_ids, existing_site_ids
                )
                total_sites_created += created
                progress_bar.update(len(batch))

        # Delete sites that weren't in the input
        sites_to_delete = existing_site_ids - seen_site_ids
        total_sites_deleted = 0
        if sites_to_delete and delete_missing:
            ChargingSite.objects.filter(id__in=sites_to_delete).delete()
            total_sites_deleted = len(sites_to_delete)

        logging.info(
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
    batch_size = 1000

    with transaction.atomic():
        with tqdm(desc="Syncing statuses", disable=None) as progress_bar:
            for batch in batched(statuses, batch_size):
                statuses_created = _sync_statuses_batch(
                    realtime_data_source, chargepoint_data_source, batch
                )
                total_statuses_created += statuses_created
                progress_bar.update(len(batch))

        logging.info(f"Created {total_statuses_created} statuses")


def _sync_statuses_batch(
    realtime_data_source: str,
    chargepoint_data_source: str,
    batch: Tuple[Tuple[str, RealtimeStatus], ...],
) -> int:
    """
    Sync a batch of statuses using bulk operations.
    Returns the number of statuses created in this batch.
    """
    # Fetch all chargepoint IDs for this batch in one lightweight query
    cp_rows = Chargepoint.objects.filter(
        site__data_source=chargepoint_data_source,
        site__id_from_source__in=[site_id for site_id, _ in batch],
    ).values_list("site__id_from_source", "id_from_source", "id")

    # Build a mapping of (site_id_from_source, chargepoint_id_from_source) -> chargepoint_id
    chargepoint_map = {
        (site_id_from_source, cp_id_from_source): cp_id
        for site_id_from_source, cp_id_from_source, cp_id in cp_rows
    }

    # Fetch the latest status for each chargepoint
    cp_ids = list(chargepoint_map.values())
    latest_statuses_qs = distinct_on(
        RealtimeStatus.objects.filter(
            data_source=realtime_data_source,
            chargepoint_id__in=cp_ids,
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
        cp_id = chargepoint_map.get(cp_key)

        if cp_id is None:
            logging.warning(
                f"Chargepoint {site_id}/{status.chargepoint.id_from_source} not found, ignoring status update"
            )
            continue

        latest_status = latest_status_map.get(cp_id)

        if latest_status is None or (
            status.timestamp > latest_status.timestamp
            and status.status != latest_status.status
        ):
            status.chargepoint_id = cp_id
            status.data_source = realtime_data_source
            statuses_to_create.append(status)

    # Bulk insert new statuses using COPY for speed
    if statuses_to_create:
        pgbulk.copy(RealtimeStatus, statuses_to_create)

    return len(statuses_to_create)
