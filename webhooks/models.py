from django.db import models

class Settings(models.Model):
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

class Position(models.Model):
    ticker = models.CharField(max_length=255)
    timeframe = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=30, decimal_places=20)
    quantity_usdt = models.DecimalField(max_digits=30, decimal_places=20)
    avg_buy_price = models.DecimalField(max_digits=30, decimal_places=20)
    avg_sell_price = models.DecimalField(max_digits=30, decimal_places=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f'{self.ticker} {self.timeframe}'
    