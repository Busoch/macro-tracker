from rest_framework.routers import DefaultRouter
from .views import FoodItemViewSet, FoodEntryViewSet, log_food, daily_summaries, register_user
from django.urls import path

router = DefaultRouter()
router.register(r"food-items", FoodItemViewSet, basename="fooditem")
router.register(r"entries", FoodEntryViewSet, basename="foodentry")

urlpatterns = [
    path("log-food/", log_food, name="log_food"),
    path("entries/daily-summaries/", daily_summaries, name="daily-summaries"),
    path("register_user/", register_user, name="register_user"),

] + router.urls
