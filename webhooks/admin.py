from django.contrib import admin
from .models import Settings, Position

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')
    list_filter = ('key',)
    search_fields = ('key', 'value')
    ordering = ('key',)
    
    fieldsets = (
        ('Configuration', {
            'fields': ('key', 'value')
        }),
    )

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'timeframe', 'quantity', 'quantity_usdt', 'avg_buy_price', 'avg_sell_price', 'created_at', 'updated_at')
    list_filter = ('ticker', 'timeframe', 'created_at')
    search_fields = ('ticker', 'timeframe')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Position Details', {
            'fields': ('ticker', 'timeframe')
        }),
        ('Quantities', {
            'fields': ('quantity', 'quantity_usdt')
        }),
        ('Prices', {
            'fields': ('avg_buy_price', 'avg_sell_price')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('created_at',)
        return self.readonly_fields
