from typing import Tuple

from ninja import NinjaAPI
from ninja.orm import register_field

api = NinjaAPI(urls_namespace="evmap")

register_field("PointField", Tuple[float, float])

# Import endpoint modules to register routes
from . import ge_realtime, site_detail, sites  # noqa: E402, F401
