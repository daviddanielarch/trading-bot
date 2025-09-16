from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging
from bingx_client import BingXClient
from webhooks.models import Position, Settings
logger = logging.getLogger(__name__)

POSITION_USDT = 100


@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler(request):
    """
    Handle incoming webhook POST requests.
    
    This view processes webhook data and can be extended to handle
    different types of webhook events based on your needs.
    """
    data = request.body
    logger.info(f"Webhook received: {data}")
    ticker, side, time_frame, use_demo = data.split(',')
    client = BingXClient(demo=use_demo)
    if Settings.objects.get(key='trading_enabled').value != 'true':
        return JsonResponse({'status': 'success'})

    if side == 'BUY':
        price = client.get_price(ticker)
        quantity = POSITION_USDT / price
        response = client.place_order(
            symbol=ticker,
            side='BUY',
            order_type='MARKET',
            positionSide='LONG',
            quantity=quantity
        )
        avg_price = response['data']['order']['avgPrice']
        Position.objects.create(
            ticker=ticker,
            timeframe=time_frame,
            avg_buy_price=avg_price,
            quantity=quantity,
            quantity_usdt=POSITION_USDT
        )
    elif side == 'SELL':
        position = Position.objects.get(ticker=ticker, timeframe=time_frame)
        response = client.place_order(
            symbol=ticker,
            side='SELL',
            order_type='MARKET',
            positionSide='LONG',
            quantity=position.quantity
        )

    return JsonResponse({'status': 'success'})