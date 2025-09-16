import requests
import time
import hmac
import hashlib
from urllib.parse import urlencode
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BingXClient:
    """
    BingX API Client for trading operations
    """
    
    def __init__(self, api_key: str = None, secret_key: str = None, demo: bool = False):
        self.api_key = api_key or os.getenv('API_KEY')
        self.secret_key = secret_key or os.getenv('SECRET_KEY')
        if demo:
            self.base_url = os.getenv('BASE_URL_DEMO', 'https://open-api-vst.bingx.com')
        else:
            self.base_url = os.getenv('BASE_URL', 'https://open-api.bingx.com')
        
        if not self.api_key or not self.secret_key:
            raise ValueError("API key and secret key are required")
    
    def _generate_signature(self, params: str) -> str:
        """Generate HMAC SHA256 signature for API requests"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _parse_params(self, params: Dict[str, Any]) -> str:
        """Parse parameters into sorted query string with timestamp"""
        sorted_keys = sorted(params.keys())
        params_str = "&".join(["%s=%s" % (x, params[x]) for x in sorted_keys])
        
        if params_str != "":
            return params_str + "&timestamp=" + str(int(time.time() * 1000))
        else:
            return params_str + "timestamp=" + str(int(time.time() * 1000))
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate headers for API requests"""
        return {
            'X-BX-APIKEY': self.api_key
        }
    
    def _make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, signed: bool = True) -> Dict[str, Any]:
        """Make authenticated request to BingX API"""
        if params is None:
            params = {}
        
        headers = self._get_headers()
        
        if signed:
            # Parse parameters into sorted query string with timestamp
            params_str = self._parse_params(params)
            # Generate signature
            signature = self._generate_signature(params_str)
            # Build URL with signature
            url = f"{self.base_url}{endpoint}?{params_str}&signature={signature}"
        else:
            # For unsigned requests, just add params to URL
            if params:
                query_string = urlencode(params)
                url = f"{self.base_url}{endpoint}?{query_string}"
            else:
                url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, data={})
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def get_price(self, symbol: str) -> Dict[str, Any]:
        """
        Get the current price of a symbol
        """
        params = {
            'symbol': symbol
        }
        return self._make_request('GET', '/openApi/swap/v1/ticker/price', params)['data']['price']
    
    def place_order(self, symbol: str, side: str, order_type: str, positionSide: str, quantity: float, 
                   price: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """
        Place a trading order
        
        Args:
            symbol: Trading pair (e.g., 'BTC-USDT')
            side: 'BUY' or 'SELL'
            order_type: 'LIMIT', 'MARKET', etc.
            quantity: Order quantity
            price: Order price (required for LIMIT orders)
            **kwargs: Additional order parameters
        """
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'positionSide': positionSide,
            'quantity': str(quantity),
            **kwargs
        }
        
        if price is not None:
            params['price'] = str(price)
        
        return self._make_request('POST', '/openApi/swap/v2/trade/order', params)
    
    def close_position(self, order_id: str) -> Dict[str, Any]:
        """
        Close a position
        """
        params = {
            'positionId': order_id,
            'timestamp': str(int(time.time() * 1000))
        }
        return self._make_request('POST', '/openApi/swap/v1/trade/closePosition', params)