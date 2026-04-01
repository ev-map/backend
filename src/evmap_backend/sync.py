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
    progress_bar: tqdm,
) -> int:
    """
    Sync a batch of sites with their chargepoints and connectors using pgbulk.upsert.
    Returns the number of sites created in this batch.
    """
    site_fields, cp_fields, conn_fields = _get_cached_update_fields()

    # Prepare sites
    for site, _ in batch:
        site.data_source = data_source

    # Upsert sites
    upserted_sites = pgbulk.upsert(
        ChargingSite,
        [site for site, _ in batch],
        ["data_source", "id_from_source"],
        site_fields,
        returning=True,
    )

    site_map = {s.id_from_source: s for s in upserted_sites}
    sites_created = len(upserted_sites.created)
    seen_site_ids.update(s.id for s in upserted_sites)

    # Collect and prepare chargepoints
    all_chargepoints = []
    cp_connectors = []  # parallel list of connector lists

    for site_data, chargepoints_data in batch:
        site = site_map[site_data.id_from_source]
        for cp, connectors in chargepoints_data:
            cp.site_id = site.id
            all_chargepoints.append(cp)
            cp_connectors.append(connectors)

    batch_site_ids = [s.id for s in upserted_sites]

    if all_chargepoints:
        # Upsert chargepoints
        upserted_cps = pgbulk.upsert(
            Chargepoint,
            all_chargepoints,
            ["site", "id_from_source"],
            cp_fields,
            returning=True,
        )

        cp_map = {(cp.site_id, cp.id_from_source): cp for cp in upserted_cps}

        # Delete chargepoints not in the input
        Chargepoint.objects.filter(site_id__in=batch_site_ids).exclude(
            id__in=[cp.id for cp in upserted_cps]
        ).delete()

        # Process connectors
        _sync_connectors(
            all_chargepoints,
            cp_connectors,
            cp_map,
            [cp.id for cp in upserted_cps],
            conn_fields,
        )
    else:
        # No chargepoints — delete all existing ones for these sites
        Chargepoint.objects.filter(site_id__in=batch_site_ids).delete()

    progress_bar.update(len(batch))
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
        resolved_cp = cp_map[(original_cp.site_id, original_cp.id_from_source)]

        if connectors and all(c.id_from_source is not None for c in connectors):
            for conn in connectors:
                conn.chargepoint_id = resolved_cp.id
            connectors_with_ids.extend(connectors)
        else:
            connectors_without_ids_data.append((resolved_cp, connectors))

    # Upsert connectors that have IDs
    upserted_connector_ids = set()
    if connectors_with_ids:
        upserted = pgbulk.upsert(
            Connector,
            connectors_with_ids,
            ["chargepoint", "id_from_source"],
            conn_update_fields,
            returning=True,
        )
        upserted_connector_ids = {c.id for c in upserted}

    # Handle connectors without IDs (fallback: compare and replace if changed)
    keep_connector_ids = set()
    connectors_to_create = []

    if connectors_without_ids_data:
        no_id_cp_ids = [cp.id for cp, _ in connectors_without_ids_data]
        existing_connectors = list(
            Connector.objects.filter(chargepoint_id__in=no_id_cp_ids)
        )
        existing_by_cp = {}
        for conn in existing_connectors:
            existing_by_cp.setdefault(conn.chargepoint_id, []).append(conn)

        for cp, new_connectors in connectors_without_ids_data:
            existing = existing_by_cp.get(cp.id, [])
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
                    conn.chargepoint_id = cp.id
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


def sync_chargers(
    data_source: str,
    sites: Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]],
    delete_missing: bool = True,
):
    """
    Sync charging sites from a data source using pgbulk upsert.
    Processes sites in batches of 100 for efficiency.
    """
    with transaction.atomic():
        existing_site_ids = set(
            ChargingSite.objects.filter(data_source=data_source).values_list(
                "id", flat=True
            )
        )
        seen_site_ids = set()
        total_sites_created = 0

        batch_size = 100
        with tqdm(desc="Syncing sites", disable=None) as progress_bar:
            for batch in batched(sites, batch_size):
                created = _sync_batch(data_source, batch, seen_site_ids, progress_bar)
                total_sites_created += created

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
    batch_size = 100

    with transaction.atomic():
        for batch in tqdm(
            batched(statuses, batch_size), desc="Syncing statuses", disable=None
        ):
            statuses_created = _sync_statuses_batch(
                realtime_data_source, chargepoint_data_source, batch
            )
            total_statuses_created += statuses_created

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

        if (
            latest_status is None
            or status.timestamp > latest_status.timestamp
            and status.status != latest_status.status
        ):
            status.chargepoint = chargepoint
            status.data_source = realtime_data_source
            statuses_to_create.append(status)

    # Bulk insert new statuses using COPY for speed
    if statuses_to_create:
        pgbulk.copy(RealtimeStatus, statuses_to_create)

    return len(statuses_to_create)
