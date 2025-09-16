from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from functools import wraps
import logging
from bingx_client import BingXClient
from webhooks.models import Position
from decimal import Decimal
from datetime import datetime
logger = logging.getLogger(__name__)

POSITION_USDT = Decimal(100)

# Allowed IP addresses for webhook access
TRADINGVIEW_IPS = [
    '52.89.214.238',
    '34.212.75.30', 
    '54.218.53.128',
    '52.32.178.7'
]


def ip_whitelist(allowed_ips):
    """
    Decorator to restrict access to specific IP addresses.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get client IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                client_ip = x_forwarded_for.split(',')[0].strip()
            else:
                client_ip = request.META.get('REMOTE_ADDR')
            
            # Check if IP is in whitelist
            if client_ip not in allowed_ips:
                logger.warning(f"Unauthorized webhook access attempt from IP: {client_ip}")
                return JsonResponse({'status': 'Unauthorized'}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@csrf_exempt
@require_http_methods(["POST"])
@ip_whitelist(TRADINGVIEW_IPS)
def webhook_handler(request):
    """
    Handle incoming webhook POST requests.
    
    This view processes webhook data and can be extended to handle
    different types of webhook events based on your needs.
    """
    data = request.body
    logger.info(f"Webhook received: {data}")
    try:
        ticker, side, time_frame, use_demo = data.decode('utf-8').split(',')
    except Exception as e:
        logger.error(f"Invalid data format: {data} - {e}")
        return JsonResponse({'status': 'Invalid data format'}, status=400)

    client = BingXClient(demo=use_demo)

    if side == 'BUY':
        # Only one position can be open at a time
        if Position.objects.filter(ticker=ticker, timeframe=time_frame, closed_at__isnull=True).exists():
            return JsonResponse({'status': 'Position already exists'}, status=400)


        price = client.get_price(ticker)
        quantity = POSITION_USDT / Decimal(price)
        response = client.place_order(
            symbol=ticker,
            side='BUY',
            order_type='MARKET',
            positionSide='LONG',
            quantity=quantity
        )
        print(response)
        avg_price = Decimal(response['data']['order']['avgPrice'])
        executed_quantity = Decimal(response['data']['order']['executedQty'])
        executed_quantity_usdt = avg_price * executed_quantity
        Position.objects.create(
            ticker=ticker,
            timeframe=time_frame,
            avg_buy_price=avg_price,
            quantity=executed_quantity,
            quantity_usdt=executed_quantity_usdt
        )
    elif side == 'SELL':
        try:
            position = Position.objects.get(ticker=ticker, timeframe=time_frame, closed_at__isnull=True)
        except Position.DoesNotExist:
            return JsonResponse({'status': 'Position does not exist'}, status=400)

        response = client.place_order(
            symbol=ticker,
            side='SELL',
            order_type='MARKET',
            positionSide='LONG',
            quantity=position.quantity
        )

        avg_price = response['data']['order']['avgPrice']
        position.avg_sell_price = avg_price
        position.closed_at = datetime.now()
        position.save()

    return JsonResponse({'status': 'success'})