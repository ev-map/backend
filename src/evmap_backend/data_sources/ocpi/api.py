import datetime as dt
import logging
import os

import pytz
from django.core.exceptions import BadRequest
from ninja import NinjaAPI
from ninja.errors import ValidationError

from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.ocpi.model import *
from evmap_backend.data_sources.ocpi.models import OcpiConnection, generate_token
from evmap_backend.data_sources.ocpi.source import BaseOcpiConnectionDataSource
from evmap_backend.data_sources.ocpi.utils import OcpiTokenAuth, ocpi_get
from evmap_backend.data_sources.registry import get_data_source

SUPPORTED_OCPI_VERSIONS = ["2.3.0", "2.2.1"]

api = NinjaAPI(urls_namespace="ocpi", auth=OcpiTokenAuth())


@api.exception_handler(ValidationError)
def custom_validation_errors(request, exc):
    print(request.body)
    logging.error(exc.errors)
    return api.create_response(request, {"detail": exc.errors}, status=422)


@api.get(
    "/versions",
    response=OcpiResponse[List[OcpiVersion]],
    auth=OcpiTokenAuth(allow_token_a=True),
)
def versions(request):
    return OcpiResponse(
        data=[
            OcpiVersion(
                version=version,
                url=request.build_absolute_uri(f"/ocpi/{version}"),
            )
            for version in SUPPORTED_OCPI_VERSIONS
        ],
        status_code=1000,
        status_message="Success",
        timestamp=dt.datetime.now(pytz.UTC),
    )


@api.get(
    "/{ocpi_version}",
    response=OcpiResponse[OcpiVersionDetail],
    auth=OcpiTokenAuth(allow_token_a=True),
)
def version_detail(request, ocpi_version: str):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    return OcpiResponse(
        data=OcpiVersionDetail(
            version=ocpi_version,
            endpoints=[
                OcpiEndpoint(
                    identifier="credentials",
                    role="RECEIVER",
                    url=request.build_absolute_uri(f"/ocpi/{ocpi_version}/credentials"),
                ),
                OcpiEndpoint(
                    identifier="locations",
                    role="RECEIVER",
                    url=request.build_absolute_uri(f"/ocpi/{ocpi_version}/locations"),
                ),
                OcpiEndpoint(
                    identifier="tariffs",
                    role="RECEIVER",
                    url=request.build_absolute_uri(f"/ocpi/{ocpi_version}/tariffs"),
                ),
            ],
        ),
        status_code=1000,
        status_message="Success",
        timestamp=dt.datetime.now(pytz.UTC),
    )


@api.post(
    "/{ocpi_version}/credentials",
    response=OcpiResponse[OcpiCredentials],
    auth=OcpiTokenAuth(allow_token_a=True),
)
def post_credentials(request, ocpi_version: str, credentials: OcpiCredentials):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth
    creds.token_b = credentials.token
    creds.url = credentials.url
    creds.country_code = credentials.roles[0].country_code
    creds.party_id = credentials.roles[0].party_id
    creds.save()

    response = ocpi_get(credentials.url, creds.token_b)
    versions = response["data"]
    version = next(v for v in versions if v["version"] == ocpi_version)
    creds.version = version["version"]

    creds.token_c = generate_token()
    creds.save()

    return OcpiResponse(
        data=OcpiCredentials(
            token=creds.token_c,
            url=request.build_absolute_uri("/ocpi/versions"),
            roles=[
                OcpiCredentialsRole(
                    role="NSP",
                    party_id=os.environ["OCPI_PARTY_ID"],
                    country_code=os.environ["OCPI_COUNTRY_CODE"],
                    business_details=OcpiBusinessDetails(
                        name=os.environ["OCPI_BUSINESS_NAME"],
                    ),
                )
            ],
        ),
        status_code=1000,
        status_message="Success",
        timestamp=dt.datetime.now(pytz.UTC),
    )


@api.api_operation(
    ["PUT", "PATCH"],
    "/{ocpi_version}/locations/{country_code}/{party_id}/{location_id}",
)
def put_location(
    request, ocpi_version: str, country_code: str, party_id: str, location_id: str
):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth

    raise NotImplementedError()


@api.put("/{ocpi_version}/locations/{country_code}/{party_id}/{location_id}/{evse_uid}")
def patch_evse(
    request,
    ocpi_version: str,
    country_code: str,
    party_id: str,
    location_id: str,
    evse_uid: str,
    evse: OcpiEvse,
):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth

    raise NotImplementedError()


@api.patch(
    "/{ocpi_version}/locations/{country_code}/{party_id}/{location_id}/{evse_uid}"
)
def patch_evse(
    request,
    ocpi_version: str,
    country_code: str,
    party_id: str,
    location_id: str,
    evse_uid: str,
    evse: PatchOcpiEvse,
):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth
    source: BaseOcpiConnectionDataSource = get_data_source(creds.data_source)

    try:
        chargepoint = Chargepoint.objects.get(
            site__id_from_source=location_id, id_from_source=evse_uid
        )
        if chargepoint.site.data_source != creds.data_source:
            raise BadRequest(
                "Chargepoint does not belong to the authenticated data source"
            )

        RealtimeStatus(
            chargepoint=chargepoint,
            status=status_mapping[evse.status],
            timestamp=evse.last_updated,
            data_source=chargepoint.site.data_source,
            license_attribution=source.license_attribution,
            license_attribution_link=none_to_blank(source.license_attribution_link),
        ).save()

        UpdateState(data_source=source.id, push=True).save()

    except Chargepoint.DoesNotExist:
        raise BadRequest("received evse patch for non-existing evse")


@api.api_operation(
    ["POST", "PATCH"],
    "/{ocpi_version}/locations/{country_code}/{party_id}/{location_id}/{evse_uid}/{connector_id}",
)
def put_connector(
    request,
    ocpi_version: str,
    country_code: str,
    party_id: str,
    location_id: str,
    evse_uid: str,
    connector_id: str,
):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth

    raise NotImplementedError()


@api.put("/{ocpi_version}/tariffs/{country_code}/{party_id}/{tariff_id}")
def put_tariff(
    request, ocpi_version: str, country_code: str, party_id: str, tariff_id: str
):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth

    raise NotImplementedError()


@api.delete("/{ocpi_version}/tariffs/{country_code}/{party_id}/{tariff_id}")
def delete_tariff(
    request, ocpi_version: str, country_code: str, party_id: str, tariff_id: str
):
    if ocpi_version not in SUPPORTED_OCPI_VERSIONS:
        raise BadRequest(f"Unsupported OCPI version: {ocpi_version}")

    creds: OcpiConnection = request.auth

    raise NotImplementedError()
