from typing import List, Tuple

from ninja import NinjaAPI, Schema

api = NinjaAPI(urls_namespace="evmap")


class LocationSchema:
    location: Tuple[float, float]


class LocationsSchema(Schema):
    count: int
    elements: List[LocationSchema]


# @api.get("/locations", response=LocationsSchema):
