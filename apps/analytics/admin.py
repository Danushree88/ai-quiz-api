from django.contrib import admin
from apps.analytics.models import UserAnalytics


@admin.register(UserAnalytics)
class UserAnalyticsAdmin(admin.ModelAdmin):
    list_display = ["user", "total_attempts", "avg_score", "updated_at"]
    readonly_fields = ["updated_at"]