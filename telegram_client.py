"""
Telegram client for sending trading bot notifications.
"""
import os
import logging
import requests
from typing import Optional
logger = logging.getLogger(__name__)


class TelegramClient:
    """
    A client for sending notifications via Telegram Bot API.
    """
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize the Telegram client.
        
        Args:
            bot_token: Telegram bot token (if not provided, will use environment variable)
            chat_id: Telegram chat ID (if not provided, will use environment variable)
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not found in environment variables")
        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID not found in environment variables")
    
    def send_message(self, text: str, parse_mode: str = "HTML", disable_notification: bool = False) -> bool:
        """
        Send a text message to the configured chat.
        
        Args:
            text: Message text to send
            parse_mode: Parse mode for the message (HTML, Markdown, or None)
            disable_notification: Whether to disable notification sound
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram bot token or chat ID not configured")
            return False
        
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': self.chat_id,
            'text': text,
            'disable_notification': disable_notification
        }
        
        if parse_mode:
            data['parse_mode'] = parse_mode
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.info(f"Telegram message sent successfully: {text[:50]}...")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    