from django.contrib.gis.measure import D
from django.core.management import BaseCommand
from django.db import transaction
from tqdm import tqdm

from evmap_backend.aggregator.models import EVSE, ChargeLocation, Connector
from evmap_backend.data_sources.datex2.models import Datex2EnergyInfrastructureSite
from evmap_backend.data_sources.goingelectric.models import GoingElectricChargeLocation

MAX_DISTANCE_METERS = 250


class Command(BaseCommand):
    help = "Updates matching of chargepoints"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for ge_location in tqdm(
            GoingElectricChargeLocation.objects.filter(aggregated_location=None)
        ):
            candidates = ChargeLocation.objects.filter(
                position__distance_lte=(
                    ge_location.coordinates,
                    D(m=MAX_DISTANCE_METERS),
                ),
                source_goingelectric=None,
            )
            if len(candidates) > 0:
                print(ge_location, ge_location.name, ge_location.coordinates)
                for candidate in candidates:
                    print(candidate, candidate.name, candidate.position)
                raise NotImplementedError("found candidates")

            with transaction.atomic():
                agg_location = ChargeLocation(
                    name=ge_location.name,
                    position=ge_location.coordinates,
                    network=ge_location.network,
                )
                agg_location.save()

                for ge_cp in ge_location.chargepoints.all():
                    for i in range(ge_cp.count):
                        agg_evse = EVSE(chargelocation=agg_location)
                        agg_evse.save()
                        agg_connector = Connector(
                            evse=agg_evse,
                            type=ge_cp.map_connector_type(),
                            power=ge_cp.power,
                        )
                        agg_connector.save()

                ge_location.aggregated_location = agg_location
                ge_location.save()

        # candidates = Datex2EnergyInfrastructureSite.objects.filter(location__distance_lte=(ge_location.coordinates, D(m=MAX_DISTANCE_METERS)))
        # if len(candidates) > 0:
        #     print(ge_location)
        #     print(candidates)
        #     break
