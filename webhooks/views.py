from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from functools import wraps
import logging
import yaml
from bingx_client import BingXClient
from liftoff.settings import WEBHOOK_IP_ALLOWED
from webhooks.models import Position, Settings
from decimal import Decimal
from datetime import datetime
from telegram_client import TelegramClient
from django.conf import settings

POSITION_USDT = Decimal(100)

logger = logging.getLogger(__name__)
telegram_client = TelegramClient(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)


def ip_whitelist(allowed_ips):
    """
    Decorator to restrict access to specific IP addresses.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                client_ip = x_forwarded_for.split(',')[0].strip()
            else:
                client_ip = request.META.get('REMOTE_ADDR')
            
            if not allowed_ips:
                return view_func(request, *args, **kwargs)
            
            if client_ip not in allowed_ips:
                logger.warning(f"Unauthorized webhook access attempt from IP: {client_ip}")
                return JsonResponse({'status': 'Unauthorized'}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@csrf_exempt
@require_http_methods(["POST"])
@ip_whitelist(WEBHOOK_IP_ALLOWED)
def webhook_handler(request):
    """
    Handle incoming webhook POST requests.
    
    This view processes webhook data in YAML format and can be extended to handle
    different types of webhook events based on your needs.
    """
    data = request.body
    logger.info(f"Webhook received: {data}")
    try:
        # Parse YAML data
        yaml_data = yaml.safe_load(data.decode('utf-8'))
        
        # Extract required fields from YAML
        ticker = yaml_data.get('ticker')
        side = yaml_data.get('side')
        time_frame = yaml_data.get('timeframe')
        use_demo = yaml_data.get('use_demo', False)
        
        # Validate required fields
        if not all([ticker, side, time_frame]):
            raise ValueError("Missing required fields: ticker, side, timeframe")
            
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML format: {data} - {e}")
        return JsonResponse({'status': 'Invalid YAML format'}, status=400)
    except Exception as e:
        logger.error(f"Invalid data format: {data} - {e}")
        return JsonResponse({'status': 'Invalid data format'}, status=400)

    trading_enabled = Settings.objects.get(key='trading_enabled').value == 'true'
    if not trading_enabled:
        logger.warning("Trading is not enabled")
        return JsonResponse({'status': 'Trading is not enabled'}, status=400)

    client = BingXClient(demo=use_demo)

    if side == 'BUY':
        # Only one position can be open at a time
        if Position.objects.filter(ticker=ticker, timeframe=time_frame, closed_at__isnull=True).exists():
            logger.warning(f"Position already exists for {ticker} {time_frame}")
            return JsonResponse({'status': 'Position already exists'}, status=400)

        price = client.get_price(ticker)
        position_usdt = Decimal(Settings.objects.get(key='position_usdt').value)
        quantity = position_usdt / Decimal(price)
        response = client.place_order(
            symbol=ticker,
            side='BUY',
            order_type='MARKET',
            positionSide='LONG',
            quantity=quantity
        )

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
            logger.warning(f"Position does not exist for {ticker} {time_frame}")
            return JsonResponse({'status': 'Position does not exist'}, status=400)

        price = Decimal(client.get_price(ticker))
        if price < position.avg_buy_price:
            logger.warning(f"Price is less than average buy price for {ticker} {time_frame}")
            telegram_client.send_message(f"Price is less than average buy price for {ticker} {time_frame}")
            return JsonResponse({'status': 'Price is less than average buy price'}, status=400)

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