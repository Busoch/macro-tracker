from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class FoodItem(models.Model):
    """
    Cached food item from external API (USDA FDC, Nutritionix, etc).
    Stores per-100g macros as canonical reference.
    """
    source = models.CharField(max_length=50)  # e.g. 'usda', 'nutritionix'
    source_food_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID from the API (nullable for custom/local foods)"
    )
    name = models.CharField(max_length=255)
    serving_size_g = models.FloatField(
        null=True, blank=True,
        help_text="Typical serving mass in grams if provided by source"
    )

    # macros per 100g (float) -- store as grams per 100g
    carbs_per_100g = models.FloatField(default=0.0, validators=[MinValueValidator(0.0)])
    protein_per_100g = models.FloatField(default=0.0, validators=[MinValueValidator(0.0)])
    fat_per_100g = models.FloatField(default=0.0, validators=[MinValueValidator(0.0)])
    calories_per_100g = models.FloatField(default=0.0, validators=[MinValueValidator(0.0)])

    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("source", "source_food_id")
        indexes = [
            models.Index(fields=["source", "source_food_id"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.source})"

    def macros_for_grams(self, grams: float):
        """
        Return computed macros for a given grams based on per-100g values.
        Returns dict with keys: carbs_g, protein_g, fat_g, calories.
        """
        factor = grams / 100.0
        carbs = round(self.carbs_per_100g * factor, 6)
        protein = round(self.protein_per_100g * factor, 6)
        fat = round(self.fat_per_100g * factor, 6)
        calories = round(self.calories_per_100g * factor, 6)
        return {
            "carbs_g": carbs,
            "protein_g": protein,
            "fat_g": fat,
            "calories": calories,
        }


class FoodEntry(models.Model):
    """
    Log of a food the user consumed.
    Stores a snapshot of macros & calories at the time of logging to preserve historical accuracy.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="food_entries")
    date = models.DateField(db_index=True)  # the day this entry counts toward
    timestamp = models.DateTimeField(default=timezone.now)

    # optional link to a cached FoodItem
    food_item = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)  # user-visible name/sourced name

    # how much was consumed (grams)
    weight_g = models.FloatField(validators=[MinValueValidator(0.01)])

    # snapshot of macros (grams) and calories (kcal)
    carbs_g = models.FloatField(validators=[MinValueValidator(0.0)])
    protein_g = models.FloatField(validators=[MinValueValidator(0.0)])
    fat_g = models.FloatField(validators=[MinValueValidator(0.0)])
    calories = models.FloatField(validators=[MinValueValidator(0.0)])

    # metadata
    serving_description = models.CharField(max_length=200, blank=True)  # e.g. "1 medium (118g)"
    source = models.CharField(max_length=50, blank=True)  # where the data came from
    source_food_id = models.IntegerField(null=True, blank=True)  # <-- allow empty

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["user", "date"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} - {self.name} ({self.date})"

    def clean(self):
        # enforce consistency: calories must equal calculation unless explicitly overridden
        computed = round(self.carbs_g * 4.0 + self.protein_g * 4.0 + self.fat_g * 9.0, 6)
        # allow minor rounding differences up to 0.01 kcal
        if abs(self.calories - computed) > 0.01:
            raise ValueError(
                f"Inconsistent calories value. Expected ~{computed} kcal "
                f"from macros, got {self.calories} kcal."
            )


class DailySummary(models.Model):
    """
    Optional denormalized totals for a user/day to speed reads.
    Keep this in sync with signals or transactions when creating/updating/deleting FoodEntry.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="daily_summaries")
    date = models.DateField(db_index=True)
    total_calories = models.FloatField(default=0.0)
    total_carbs_g = models.FloatField(default=0.0)
    total_protein_g = models.FloatField(default=0.0)
    total_fat_g = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user} summary {self.date}"
