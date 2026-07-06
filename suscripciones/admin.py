from django.contrib import admin
from .models import Subscription, SubscriptionConfig


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'start_date', 'end_date', 'active', 'is_valid')
    list_filter   = ('active',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('is_valid',)


@admin.register(SubscriptionConfig)
class SubscriptionConfigAdmin(admin.ModelAdmin):
    list_display = ('default_start_date', 'default_end_date', 'active')
