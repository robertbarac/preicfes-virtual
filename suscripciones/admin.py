from django.contrib import admin
from .models import Subscription

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_date', 'end_date', 'active', 'is_valid']
    list_filter = ['active', 'start_date', 'end_date']
    search_fields = ['user__username', 'user__email']
    date_hierarchy = 'start_date'
