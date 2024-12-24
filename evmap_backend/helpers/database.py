from typing import List

from django.db.models import OuterRef, QuerySet, Subquery

from evmap_backend import settings


def distinct_on(
    queryset: QuerySet, distinct_fields: List[str], order_field: str, order_reverse=True
):
    order = f"-{order_field}" if order_reverse else order_field
    if "postgres" in settings.DATABASES["default"]["ENGINE"]:
        # use native DISTINCT BY functionality in Postgres
        return queryset.order_by(*distinct_fields, order).distinct(*distinct_fields)
    else:
        # Use subquery to find first element by order_field for each distinct_field
        subquery = (
            queryset.filter(**{f: OuterRef(f) for f in distinct_fields})
            .order_by(order)
            .values(order_field)[:1]
        )
        # filter using the subquery
        return queryset.filter(**{order_field: Subquery(subquery)})
