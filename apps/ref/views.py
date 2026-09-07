from django.db.models import Exists, OuterRef
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.ref.models import District, Province, Tehsil, Tribe, TribeDistrict
from apps.ref.serializers import RefOptionSerializer

REF_CACHE = "public, s-maxage=86400, stale-while-revalidate=604800"


def cached(data, status=200):
    response = Response(data, status=status)
    response["Cache-Control"] = REF_CACHE
    return response


def option(**fields):
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


def tribe_option(tribe, has_children):
    return option(
        id=tribe.id,
        name=tribe.name,
        ps=tribe.pashto,
        aliases=tribe.aliases,
        hasChildren=has_children,
    )


@extend_schema(
    parameters=[OpenApiParameter("country", str, required=True)],
    responses=RefOptionSerializer(many=True),
)
@api_view(["GET"])
def provinces(request):
    country = request.GET.get("country")
    if not country:
        return Response({"error": "country is required"}, status=400)
    items = Province.objects.filter(country_id=country)
    ordered = sorted(items, key=lambda p: (p.id != "pk-kp", p.name))
    return cached([option(id=p.id, name=p.name) for p in ordered])


@extend_schema(
    parameters=[OpenApiParameter("province", str, required=True)],
    responses=RefOptionSerializer(many=True),
)
@api_view(["GET"])
def districts(request):
    province = request.GET.get("province")
    if not province:
        return Response({"error": "province is required"}, status=400)
    items = District.objects.filter(province_id=province).annotate(
        has_tehsils=Exists(Tehsil.objects.filter(district=OuterRef("pk"))),
    )
    return cached(
        [
            option(
                id=d.id,
                name=d.name,
                language=d.language,
                hasTehsils=d.has_tehsils,
            )
            for d in items
        ],
    )


@extend_schema(
    parameters=[OpenApiParameter("district", str, required=True)],
    responses=RefOptionSerializer(many=True),
)
@api_view(["GET"])
def tehsils(request):
    district = request.GET.get("district")
    if not district:
        return Response({"error": "district is required"}, status=400)
    items = Tehsil.objects.filter(district_id=district)
    return cached([option(id=t.id, name=t.name) for t in items])


@extend_schema(
    parameters=[
        OpenApiParameter("district", str, required=False),
        OpenApiParameter("parent", str, required=False),
    ],
    responses=RefOptionSerializer(many=True),
)
@api_view(["GET"])
def tribes(request):
    parent = request.GET.get("parent")
    district = request.GET.get("district")
    has_children = Exists(Tribe.objects.filter(parent=OuterRef("pk")))

    if parent:
        items = Tribe.objects.filter(parent_id=parent).annotate(kids=has_children)
        return cached([tribe_option(t, t.kids) for t in items])

    roots = Tribe.objects.filter(level=1).annotate(kids=has_children)
    role_rank = {"dominant": 0, "present": 1}
    ranks = {}
    if district:
        links = TribeDistrict.objects.filter(district_id=district)
        ranks = {link.tribe_id: role_rank[link.role] for link in links}
    ordered = sorted(roots, key=lambda t: (ranks.get(t.id, 2), t.name))
    return cached([tribe_option(t, t.kids) for t in ordered])
