"""
Matching algorithm to link GoingElectricChargeLocation records to ChargingSite records.

Uses a weighted scoring algorithm (distance, network, chargepoint similarity) with
global greedy 1:1 assignment to ensure deterministic results.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from django.db import connection

from evmap_backend.chargers.models import ChargingSite, Connector
from evmap_backend.data_sources.goingelectric.models import (
    GE_CONNECTOR_TYPE_MAP,
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
    GoingElectricNetwork,
)

logger = logging.getLogger(__name__)

# Weight configuration for scoring components
DISTANCE_WEIGHT = 0.4
NETWORK_WEIGHT = 0.3
CHARGEPOINT_WEIGHT = 0.3


def _score_distance(distance_m: float, max_distance_m: float) -> float:
    """Linear score from 1.0 at 0m to 0.0 at max_distance_m."""
    if distance_m >= max_distance_m:
        return 0.0
    return 1.0 - (distance_m / max_distance_m)


def _score_network(
    ge_network_id: Optional[int],
    site_network_id: Optional[int],
    network_mapping: Dict[int, Set[int]],
) -> float:
    """
    Score network match.
    1.0 if site's network is in the GE network's mapped_networks.
    0.5 if either side has no network.
    0.0 if both have networks but they don't match.
    """
    if ge_network_id is None or site_network_id is None:
        return 0.5
    mapped = network_mapping.get(ge_network_id, set())
    if not mapped:
        # GE network exists but has no mapped networks configured
        return 0.5
    return 1.0 if site_network_id in mapped else 0.0


def _score_chargepoints(
    ge_chargepoints: List[GoingElectricChargepoint],
    site_connectors: List[Connector],
) -> float:
    """
    Score chargepoint similarity between GE chargepoints and site connectors.

    For each GE chargepoint, check if there's a compatible connector on the site
    (matching type via GE_CONNECTOR_TYPE_MAP and power within factor of 2).
    Score is the fraction of GE chargepoints that find a match.

    GE chargepoints have a count field (e.g., "2x Type 2 22kW"), but we don't
    require matching counts — just that a compatible type+power exists.
    """
    if not ge_chargepoints:
        return 0.5  # No chargepoint info, neutral score

    if not site_connectors:
        return 0.0  # Site has no connectors, can't match

    # Build a set of (connector_type, max_power) for the site
    site_connector_set = [
        (conn.connector_type, conn.max_power) for conn in site_connectors
    ]

    matched = 0
    total = len(ge_chargepoints)

    for ge_cp in ge_chargepoints:
        compatible_types = GE_CONNECTOR_TYPE_MAP.get(ge_cp.type, set())
        ge_power_w = ge_cp.power * 1000  # GE power is in kW, Connector.max_power in W

        for site_type, site_power in site_connector_set:
            if site_type in compatible_types and _power_matches(ge_power_w, site_power):
                matched += 1
                break

    return matched / total


def _power_matches(power_a: float, power_b: float) -> bool:
    """Check if two power values are within a factor of 2 of each other."""
    if power_a <= 0 or power_b <= 0:
        return True  # If either is zero/unknown, don't penalize
    ratio = power_a / power_b
    return 0.5 <= ratio <= 2.0


def score_match(
    distance_m: float,
    ge_network_id: Optional[int],
    site_network_id: Optional[int],
    network_mapping: Dict[int, Set[int]],
    ge_chargepoints: List[GoingElectricChargepoint],
    site_connectors: List[Connector],
    max_distance_m: float = 200.0,
) -> float:
    """
    Compute weighted match score (0-1) for a GE location / ChargingSite pair.
    """
    dist_score = _score_distance(distance_m, max_distance_m)
    net_score = _score_network(ge_network_id, site_network_id, network_mapping)
    cp_score = _score_chargepoints(ge_chargepoints, site_connectors)

    return (
        DISTANCE_WEIGHT * dist_score
        + NETWORK_WEIGHT * net_score
        + CHARGEPOINT_WEIGHT * cp_score
    )


def _build_network_mapping() -> Dict[int, Set[int]]:
    """
    Build a lookup dict: GoingElectricNetwork.id -> set of chargers.Network.id
    from the mapped_networks M2M relationship.
    """
    mapping: Dict[int, Set[int]] = defaultdict(set)
    for ge_network in GoingElectricNetwork.objects.prefetch_related("mapped_networks"):
        for network in ge_network.mapped_networks.all():
            mapping[ge_network.id].add(network.id)
    return dict(mapping)


def _prefetch_site_connectors(site_ids: Set[int]) -> Dict[int, List[Connector]]:
    """
    Fetch all connectors for the given site IDs, grouped by site ID.
    """
    connectors_by_site: Dict[int, List[Connector]] = defaultdict(list)
    for conn in Connector.objects.filter(
        chargepoint__site_id__in=site_ids
    ).select_related("chargepoint"):
        connectors_by_site[conn.chargepoint.site_id].append(conn)
    return dict(connectors_by_site)


def match_ge_locations(
    queryset=None,
    max_distance_m: float = 200.0,
    min_confidence: float = 0.4,
):
    """
    Match GoingElectricChargeLocation records to ChargingSite records using
    a two-phase global greedy algorithm:

    1. Candidate generation: for each GE location, find nearby ChargingSites
       and score each pair.
    2. Greedy assignment: sort all pairs by score descending, assign 1:1
       (each site and each GE location used at most once).

    Args:
        queryset: Optional queryset of GoingElectricChargeLocation to match.
                  Defaults to all locations.
        max_distance_m: Maximum distance in meters for candidate search.
        min_confidence: Minimum score threshold for a match to be accepted.
    """
    if queryset is None:
        queryset = GoingElectricChargeLocation.objects.all()

    # Build network mapping once
    network_mapping = _build_network_mapping()

    # Prefetch all GE chargepoints grouped by location
    ge_chargepoints_by_location: Dict[int, List[GoingElectricChargepoint]] = (
        defaultdict(list)
    )
    for cp in GoingElectricChargepoint.objects.all():
        ge_chargepoints_by_location[cp.chargelocation_id].append(cp)

    # Phase 1: Candidate generation via single spatial join query
    all_candidate_site_ids: Set[int] = set()
    ge_candidates: Dict[
        int, Tuple[Optional[int], List[Tuple[int, float, Optional[int]]]]
    ] = {}  # ge_id -> (network_id, [(site_id, distance_m, site_network_id)])

    # Build the GE location ID filter for the queryset
    ge_ids = list(queryset.values_list("id", flat=True))
    if not ge_ids:
        logger.info("No GE locations to match.")
        return

    # Build a lookup for GE network_id by ge_id
    ge_network_by_id: Dict[int, Optional[int]] = dict(
        queryset.values_list("id", "network_id")
    )

    ge_table = GoingElectricChargeLocation._meta.db_table
    site_table = ChargingSite._meta.db_table

    # Single spatial join using ST_DWithin on geography columns.
    # With geography=True on both PointFields, PostGIS has geography GIST
    # indexes and ST_DWithin accepts meters directly.
    #
    # This uses raw SQL because the ORM's dwithin lookup filters one queryset
    # against a single point.  We need a cross-table join (all GE locations ×
    # all sites within distance) in a single query; the ORM cannot express this
    # without reverting to one query per GE location.
    logger.info("Phase 1: Finding candidates via spatial join...")
    sql = f"""
        SELECT
            ge.id                AS ge_id,
            site.id              AS site_id,
            ST_Distance(ge.coordinates, site.location) AS distance_m,
            site.network_id      AS site_network_id
        FROM {ge_table} ge
        JOIN {site_table} site
            ON ST_DWithin(ge.coordinates, site.location, %s)
        WHERE ge.id = ANY(%s)
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, [max_distance_m, ge_ids])
        rows = cursor.fetchall()

    logger.info("Spatial join returned %d candidate pairs.", len(rows))

    for ge_id, site_id, distance_m, site_network_id in rows:
        all_candidate_site_ids.add(site_id)
        if ge_id not in ge_candidates:
            ge_candidates[ge_id] = (ge_network_by_id.get(ge_id), [])
        ge_candidates[ge_id][1].append((site_id, distance_m, site_network_id))

    # Prefetch connectors for all candidate sites at once
    logger.info(
        "Prefetching connectors for %d candidate sites...", len(all_candidate_site_ids)
    )
    connectors_by_site = _prefetch_site_connectors(all_candidate_site_ids)

    # Score all pairs
    logger.info("Scoring %d GE locations with candidates...", len(ge_candidates))
    scored_pairs: List[Tuple[float, int, int]] = []  # (score, ge_id, site_id)

    for ge_id, (ge_network_id, candidate_list) in ge_candidates.items():
        ge_cps = ge_chargepoints_by_location.get(ge_id, [])

        for site_id, distance_m, site_network_id in candidate_list:
            site_connectors = connectors_by_site.get(site_id, [])
            score = score_match(
                distance_m=distance_m,
                ge_network_id=ge_network_id,
                site_network_id=site_network_id,
                network_mapping=network_mapping,
                ge_chargepoints=ge_cps,
                site_connectors=site_connectors,
                max_distance_m=max_distance_m,
            )
            if score >= min_confidence:
                scored_pairs.append((score, ge_id, site_id))

    # Phase 2: Greedy 1:1 assignment — highest scores first
    logger.info(
        "Phase 2: Greedy assignment of %d candidate pairs...", len(scored_pairs)
    )
    scored_pairs.sort(key=lambda x: x[0], reverse=True)

    claimed_ge_ids: Set[int] = set()
    claimed_site_ids: Set[int] = set()
    assignments: List[Tuple[int, int, float]] = []  # (ge_id, site_id, score)

    for score, ge_id, site_id in scored_pairs:
        if ge_id in claimed_ge_ids or site_id in claimed_site_ids:
            continue
        claimed_ge_ids.add(ge_id)
        claimed_site_ids.add(site_id)
        assignments.append((ge_id, site_id, score))

    # Apply assignments: clear all existing matches first, then set new ones
    GoingElectricChargeLocation.objects.filter(
        id__in=queryset.values_list("id", flat=True)
    ).update(matched_site=None, match_confidence=None)

    if assignments:
        # Build lightweight model instances and bulk_update in batches
        ge_to_update = []
        for ge_id, site_id, confidence in assignments:
            obj = GoingElectricChargeLocation(id=ge_id)
            obj.matched_site_id = site_id
            obj.match_confidence = confidence
            ge_to_update.append(obj)
        GoingElectricChargeLocation.objects.bulk_update(
            ge_to_update,
            fields=["matched_site_id", "match_confidence"],
            batch_size=500,
        )

    matched_count = len(assignments)
    total_count = queryset.count()
    logger.info(
        "Matching complete: %d/%d GE locations matched (%.1f%%)",
        matched_count,
        total_count,
        (matched_count / total_count * 100) if total_count else 0,
    )


def suggest_network_mappings(
    ge_network: Optional[GoingElectricNetwork] = None,
) -> Dict[int, Dict[int, int]]:
    """
    Analyse already-matched GE locations to infer which chargers.Network
    each GoingElectricNetwork should map to.

    Args:
        ge_network: If given, only return suggestions for this GE network.

    Returns:
        Dict mapping GoingElectricNetwork.id -> {chargers.Network.id: count}
        where *count* is the number of matched stations supporting that pairing.
    """
    counts: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    qs = GoingElectricChargeLocation.objects.filter(
        matched_site__isnull=False,
        network__isnull=False,
        matched_site__network__isnull=False,
    )
    if ge_network is not None:
        qs = qs.filter(network=ge_network)

    for ge_network_id, site_network_id in qs.values_list(
        "network_id", "matched_site__network_id"
    ):
        counts[ge_network_id][site_network_id] += 1

    return {k: dict(v) for k, v in counts.items()}
