import logging
from itertools import batched
from typing import Dict, Iterable, List, Tuple

from django.db import transaction
from tqdm import tqdm

from evmap_backend.chargers.models import Chargepoint
from evmap_backend.pricing.models import PriceComponent, Tariff

logger = logging.getLogger(__name__)


def _tariff_fingerprint(tariff: Tariff, components: List[PriceComponent]) -> tuple:
    """
    Create a hashable fingerprint of a tariff + components for deduplication.
    Chargepoints with the same pricing fingerprint can share a Tariff.
    """
    component_parts = []
    for c in sorted(components, key=lambda x: (x.type, str(x.price))):
        component_parts.append(
            (
                c.type,
                c.price,
                c.tax_included,
                c.tax_rate,
                c.step_size,
                c.min_price,
                c.max_price,
                c.day_of_week,
                c.time_start,
                c.time_end,
                c.min_power,
                c.max_power,
                c.min_duration,
                c.max_duration,
            )
        )
    return (
        tariff.is_adhoc,
        tariff.currency,
        tariff.id_from_source,
        tuple(component_parts),
    )


def sync_pricing(
    data_source: str,
    chargepoint_data_source: str,
    pricing_data: Iterable[Tuple[str, str, Tariff, List[PriceComponent]]],
):
    """
    Sync pricing/tariff data from any data source.

    Deduplicates tariffs by content: chargepoints with identical pricing share
    a single Tariff object. Each unique pricing fingerprint gets one Tariff.

    Args:
        data_source: ID of the pricing data source.
        chargepoint_data_source: ID of the static data source for chargepoints
            (used to look up Chargepoint objects by id_from_source).
        pricing_data: Iterable of (site_id, chargepoint_id_from_source, Tariff,
            [PriceComponent]) tuples. The Tariff and PriceComponent objects should
            be unsaved (no pk). The site_id and chargepoint_id_from_source are used
            to resolve Chargepoint objects from the database.
    """
    # Phase 1: Collect all unique tariffs and map chargepoint IDs to fingerprints
    # fingerprint -> (Tariff, [PriceComponent], set of chargepoint_ids)
    fingerprint_map: Dict[tuple, Tuple[Tariff, List[PriceComponent], set]] = {}
    # chargepoint_id -> site_id (for chargepoint lookup)
    cp_to_site: Dict[str, str] = {}

    for site_id, cp_id, tariff, components in tqdm(
        pricing_data, desc="Collecting pricing data"
    ):
        cp_to_site[cp_id] = site_id
        fp = _tariff_fingerprint(tariff, components)
        if fp not in fingerprint_map:
            fingerprint_map[fp] = (tariff, components, set())
        fingerprint_map[fp][2].add(cp_id)

    logger.info(
        f"Found {len(fingerprint_map)} unique tariff(s) across "
        f"{len(cp_to_site)} chargepoint(s)"
    )

    # Phase 2: Resolve chargepoint_ids to Chargepoint PKs
    all_cp_ids = set(cp_to_site.keys())
    all_site_ids = set(cp_to_site.values())

    chargepoint_map: Dict[str, int] = {}  # chargepoint_id_from_source -> chargepoint.pk
    for batch in batched(all_site_ids, 500):
        chargepoints = Chargepoint.objects.filter(
            site__data_source=chargepoint_data_source,
            site__id_from_source__in=batch,
        ).values_list("id_from_source", "pk")
        for id_from_source, pk in chargepoints:
            if id_from_source in all_cp_ids:
                chargepoint_map[id_from_source] = pk

    logger.info(
        f"Resolved {len(chargepoint_map)}/{len(all_cp_ids)} chargepoint(s) from DB"
    )

    # Phase 3: Create/update tariffs in a transaction
    with transaction.atomic():
        # Delete existing tariffs from this data source
        old_count, _ = Tariff.objects.filter(data_source=data_source).delete()
        if old_count:
            logger.info(f"Deleted {old_count} old tariff(s) from {data_source}")

        for fp, (tariff, components, cp_ids) in tqdm(
            fingerprint_map.items(), desc="Creating tariffs"
        ):
            tariff.data_source = data_source
            tariff.save()

            # Save components
            for component in components:
                component.tariff = tariff
            PriceComponent.objects.bulk_create(components)

            # Link chargepoints
            cp_pks = [
                chargepoint_map[cp_id] for cp_id in cp_ids if cp_id in chargepoint_map
            ]
            if cp_pks:
                tariff.chargepoints.set(cp_pks)

    logger.info(f"Synced {len(fingerprint_map)} tariff(s) for {data_source}")
