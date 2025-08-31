from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from nutrition import views as nutrition_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT authentication
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # User registration
    path("api/register_user/", nutrition_views.register_user, name="register_user"),

    # App routes
    path("api/", include("nutrition.urls")),
]
