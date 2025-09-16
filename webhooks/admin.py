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
    list_display = ('ticker', 'formatted_quantity_usdt', 'formatted_avg_buy_price', 'formatted_avg_sell_price', 'formatted_profit', 'formatted_profit_rate', 'created_at', 'closed_at', 'trade_completion_time')
    list_filter = ('ticker', 'timeframe', 'created_at')
    search_fields = ('ticker', 'timeframe')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'closed_at')
    
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
    
    def formatted_quantity(self, obj):
        """Format quantity to 6 decimal places"""
        return f"{obj.quantity:.6f}"
    formatted_quantity.short_description = 'Quantity'
    
    def formatted_quantity_usdt(self, obj):
        """Format quantity_usdt to 2 decimal places"""
        return f"{obj.quantity_usdt:.2f}"
    formatted_quantity_usdt.short_description = 'Quantity USDT'
    
    def formatted_avg_buy_price(self, obj):
        """Format avg_buy_price to 2 decimal places"""
        return f"{obj.avg_buy_price:.2f}"
    formatted_avg_buy_price.short_description = 'Avg Buy Price'
    
    def formatted_avg_sell_price(self, obj):
        """Format avg_sell_price to 2 decimal places"""
        if obj.avg_sell_price is None:
            return '-'
        return f"{obj.avg_sell_price:.2f}"
    formatted_avg_sell_price.short_description = 'Avg Sell Price'
    
    def formatted_profit(self, obj):
        """Format profit to 2 decimal places"""
        profit = obj.profit()
        if profit is None:
            return '-'
        return f"{profit:.2f}"
    formatted_profit.short_description = 'Profit (USDT)'
    
    def formatted_profit_rate(self, obj):
        """Format profit rate to 2 decimal places with % sign"""
        profit_rate = obj.profit_rate()
        if profit_rate is None:
            return '-'
        return f"{profit_rate:.2f}%"
    formatted_profit_rate.short_description = 'Profit Rate'
    
    def trade_completion_time(self, obj):
        """Format trade completion time to 2 decimal places with % sign"""
        if obj.closed_at is None:
            return '-'
        return obj.closed_at - obj.created_at
    trade_completion_time.short_description = 'Trade Completion Time'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('created_at',)
        return self.readonly_fields
