import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import status, viewsets, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.tokens import RefreshToken

from .models import FoodItem, FoodEntry, DailySummary
from .serializers import FoodItemSerializer, FoodEntrySerializer, DailySummarySerializer


class FoodItemViewSet(viewsets.ModelViewSet):
    queryset = FoodItem.objects.all()
    serializer_class = FoodItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["source"]
    search_fields = ["name"]

    @action(detail=False, methods=["get"], url_path="search")
    def search_external(self, request):
        q = request.query_params.get("q")
        if not q:
            return Response(
                {"detail": "Missing query parameter 'q'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
        headers = {
            "x-app-id": settings.NUTRITIONIX_APP_ID,
            "x-app-key": settings.NUTRITIONIX_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"query": q}

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            r.raise_for_status()
        except requests.RequestException:
            return Response(
                {"error": "Nutritionix request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = r.json()
        results = []
        for food in data.get("foods", []):
            weight = float(food.get("serving_weight_grams") or 1)
            results.append({
                "name": food.get("food_name") or q,
                "serving_weight_grams": weight,
                "calories": float(food.get("nf_calories", 0)),
                "protein_g": float(food.get("nf_protein", 0)),
                "carbs_g": float(food.get("nf_total_carbohydrate", 0)),
                "fat_g": float(food.get("nf_total_fat", 0)),
                "source": "nutritionix",
                "source_food_id": food.get("tag_id", ""),
            })

        return Response({"results": results}, status=200)


class FoodEntryViewSet(viewsets.ModelViewSet):
    serializer_class = FoodEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["date", "source"]
    ordering_fields = ["date", "timestamp"]

    def get_queryset(self):
        return FoodEntry.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._update_summary_on_create(instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            previous = FoodEntry.objects.get(pk=serializer.instance.pk)
            instance = serializer.save()
            self._update_summary_on_update(previous, instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            self._update_summary_on_delete(instance)
            instance.delete()

    def _update_summary_on_create(self, entry):
        summary, _ = DailySummary.objects.get_or_create(user=entry.user, date=entry.date)
        summary.total_calories += entry.calories or 0.0
        summary.total_carbs_g += entry.carbs_g or 0.0
        summary.total_protein_g += entry.protein_g or 0.0
        summary.total_fat_g += entry.fat_g or 0.0
        summary.save()

    def _update_summary_on_update(self, previous, updated):
        if previous.date != updated.date:
            self._update_summary_on_delete(previous)
            self._update_summary_on_create(updated)
        else:
            delta_cal = (updated.calories or 0) - (previous.calories or 0)
            delta_carbs = (updated.carbs_g or 0) - (previous.carbs_g or 0)
            delta_protein = (updated.protein_g or 0) - (previous.protein_g or 0)
            delta_fat = (updated.fat_g or 0) - (previous.fat_g or 0)

            summary, _ = DailySummary.objects.get_or_create(user=updated.user, date=updated.date)
            summary.total_calories += delta_cal
            summary.total_carbs_g += delta_carbs
            summary.total_protein_g += delta_protein
            summary.total_fat_g += delta_fat
            summary.save()

    def _update_summary_on_delete(self, entry):
        try:
            summary = DailySummary.objects.get(user=entry.user, date=entry.date)
        except DailySummary.DoesNotExist:
            return
        summary.total_calories = max(summary.total_calories - (entry.calories or 0), 0.0)
        summary.total_carbs_g = max(summary.total_carbs_g - (entry.carbs_g or 0), 0.0)
        summary.total_protein_g = max(summary.total_protein_g - (entry.protein_g or 0), 0.0)
        summary.total_fat_g = max(summary.total_fat_g - (entry.fat_g or 0), 0.0)
        summary.save()

    @action(detail=False, methods=["get"], url_path="today-summary")
    def today_summary(self, request):
        """Get aggregated macros for today (or ?date=YYYY-MM-DD)."""
        date_str = request.query_params.get("date")
        if date_str:
            from datetime import datetime
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date format; use YYYY-MM-DD."}, status=400)
        else:
            date = timezone.localdate()

        entries = FoodEntry.objects.filter(user=request.user, date=date)
        totals = entries.aggregate(
            total_calories=Sum("calories"),
            total_carbs_g=Sum("carbs_g"),
            total_protein_g=Sum("protein_g"),
            total_fat_g=Sum("fat_g"),
        )

        return Response({
            "date": date,
            "total_calories": totals["total_calories"] or 0.0,
            "total_carbs_g": totals["total_carbs_g"] or 0.0,
            "total_protein_g": totals["total_protein_g"] or 0.0,
            "total_fat_g": totals["total_fat_g"] or 0.0,
        })

    @action(detail=False, methods=["get"], url_path="today")
    def today_entries(self, request):
        """Return the list of food entries for today only."""
        today = timezone.localdate()
        entries = FoodEntry.objects.filter(user=request.user, date=today).order_by("-timestamp")
        serializer = self.get_serializer(entries, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="by-date")
    def entries_by_date(self, request):
        """Return the list of food entries for a given date (use ?date=YYYY-MM-DD)."""
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "Date query param required (YYYY-MM-DD)."}, status=400)

        from datetime import datetime
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format; use YYYY-MM-DD."}, status=400)

        entries = FoodEntry.objects.filter(user=request.user, date=date).order_by("-timestamp")
        serializer = self.get_serializer(entries, many=True)
        return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def log_food(request):
    query = request.data.get("query")
    if not query:
        return Response({"error": "No query provided"}, status=status.HTTP_400_BAD_REQUEST)

    url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    headers = {
        "x-app-id": settings.NUTRITIONIX_APP_ID,
        "x-app-key": settings.NUTRITIONIX_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"query": query}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
    except requests.RequestException:
        return Response({"error": "Nutritionix request failed"}, status=status.HTTP_502_BAD_GATEWAY)

    data = r.json()
    saved_entries = []

    for food in data.get("foods", []):
        weight = float(food.get("serving_weight_grams") or 100)
        tag_id = (food.get("tag_id") or "").strip()
        name_normalized = (food.get("food_name") or query).strip().lower()

        if tag_id:
            item, _ = FoodItem.objects.get_or_create(
                source="nutritionix",
                source_food_id=tag_id,
                defaults={
                    "name": food.get("food_name") or query,
                    "calories_per_100g": float(food.get("nf_calories", 0)) * (100 / weight),
                    "protein_per_100g": float(food.get("nf_protein", 0)) * (100 / weight),
                    "carbs_per_100g": float(food.get("nf_total_carbohydrate", 0)) * (100 / weight),
                    "fat_per_100g": float(food.get("nf_total_fat", 0)) * (100 / weight),
                }
            )
        else:
            item = FoodItem.objects.filter(
                source="nutritionix",
                name__iexact=name_normalized
            ).first()

            if not item:
                item = FoodItem.objects.create(
                    source="nutritionix",
                    source_food_id=None,
                    name=food.get("food_name") or query,
                    calories_per_100g=float(food.get("nf_calories", 0)) * (100 / weight),
                    protein_per_100g=float(food.get("nf_protein", 0)) * (100 / weight),
                    carbs_per_100g=float(food.get("nf_total_carbohydrate", 0)) * (100 / weight),
                    fat_per_100g=float(food.get("nf_total_fat", 0)) * (100 / weight),
                )

        macros = item.macros_for_grams(weight)

        entry = FoodEntry.objects.create(
            user=request.user,
            food_item=item,
            name=item.name,
            weight_g=weight,
            carbs_g=macros["carbs_g"],
            protein_g=macros["protein_g"],
            fat_g=macros["fat_g"],
            calories=macros["calories"],
            source="nutritionix",
            source_food_id=tag_id or None,
            date=timezone.now().date(),
        )

        saved_entries.append({
            "name": entry.name,
            "calories": entry.calories,
            "protein": entry.protein_g,
            "carbs": entry.carbs_g,
            "fat": entry.fat_g,
        })

    return Response({"entries": saved_entries}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def daily_summaries(request):
    summaries = (
        FoodEntry.objects.filter(user=request.user)
        .values("date")
        .annotate(
            total_calories=Sum("calories"),
            total_protein=Sum("protein_g"),
            total_carbs=Sum("carbs_g"),
            total_fat=Sum("fat_g"),
        )
        .order_by("-date")
    )
    return Response(summaries)


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already taken."}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password)
    return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)
