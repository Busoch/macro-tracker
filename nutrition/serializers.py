from rest_framework import serializers
from .models import FoodItem, FoodEntry, DailySummary
import requests
from django.conf import settings


class FoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = [
            "id", "source", "source_food_id", "name", "serving_size_g",
            "carbs_per_100g", "protein_per_100g", "fat_per_100g", "calories_per_100g",
            "last_synced",
        ]
        read_only_fields = ["id", "last_synced"]


class FoodEntrySerializer(serializers.ModelSerializer):
    # Custom input fields
    food = serializers.CharField(write_only=True)
    amount_g = serializers.FloatField(write_only=True)

    class Meta:
        model = FoodEntry
        fields = [
            "id", "date", "timestamp",
            "name", "weight_g", "carbs_g", "protein_g", "fat_g", "calories",
            "food", "amount_g",   # only for input
        ]
        read_only_fields = ["name", "weight_g", "carbs_g", "protein_g", "fat_g", "calories"]

    def create(self, validated_data):
        user = self.context["request"].user
        food_name = validated_data.pop("food")
        amount_g = validated_data.pop("amount_g")

        # 1. Try to find locally
        food_item = FoodItem.objects.filter(name__icontains=food_name).first()

        # 2. If not found, fetch from Nutritionix
        if not food_item:
            url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
            headers = {
                "x-app-id": settings.NUTRITIONIX_APP_ID,
                "x-app-key": settings.NUTRITIONIX_API_KEY,
                "Content-Type": "application/json",
            }
            payload = {"query": food_name}
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            r.raise_for_status()
            data = r.json()
            if not data.get("foods"):
                raise serializers.ValidationError({"food": f"{food_name} not found in Nutritionix"})

            f = data["foods"][0]
            weight = float(f.get("serving_weight_grams") or 100)
            food_item = FoodItem.objects.create(
                source="nutritionix",
                source_food_id=f.get("tag_id", ""),
                name=f.get("food_name") or food_name,
                calories_per_100g=float(f.get("nf_calories", 0)) * (100 / weight),
                protein_per_100g=float(f.get("nf_protein", 0)) * (100 / weight),
                carbs_per_100g=float(f.get("nf_total_carbohydrate", 0)) * (100 / weight),
                fat_per_100g=float(f.get("nf_total_fat", 0)) * (100 / weight),
            )

        # 3. Calculate macros
        macros = food_item.macros_for_grams(amount_g)

        # 4. Create entry
        entry = FoodEntry.objects.create(
            user=user,
            food_item=food_item,
            name=food_item.name,
            weight_g=amount_g,
            carbs_g=macros["carbs_g"],
            protein_g=macros["protein_g"],
            fat_g=macros["fat_g"],
            calories=macros["calories"],
            **validated_data,
        )
        return entry


class DailySummarySerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    total_calories = serializers.SerializerMethodField()
    total_carbs_g = serializers.SerializerMethodField()
    total_protein_g = serializers.SerializerMethodField()
    total_fat_g = serializers.SerializerMethodField()

    class Meta:
        model = DailySummary
        fields = [
            "id", "user", "date",
            "total_calories", "total_carbs_g", "total_protein_g", "total_fat_g",
            "updated_at"
        ]
        read_only_fields = ["id", "updated_at"]

    def get_total_calories(self, obj):
        return round(sum(entry.calories for entry in obj.user.food_entries.filter(date=obj.date)), 2)

    def get_total_carbs_g(self, obj):
        return round(sum(entry.carbs_g for entry in obj.user.food_entries.filter(date=obj.date)), 2)

    def get_total_protein_g(self, obj):
        return round(sum(entry.protein_g for entry in obj.user.food_entries.filter(date=obj.date)), 2)

    def get_total_fat_g(self, obj):
        return round(sum(entry.fat_g for entry in obj.user.food_entries.filter(date=obj.date)), 2)
