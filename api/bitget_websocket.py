import asyncio
import json
import ssl
import websockets
import certifi
from typing import Dict, Callable
from utils.logging_setup import setup_logger
from utils.unified_error_handler import UnifiedErrorHandler, ErrorType


class BitgetWebSocketClient:
    """ Упрощенный WebSocket клиент для Bitget ticker канала """
    
    def __init__(self, url: str = "wss://ws.bitget.com/v2/ws/public"):
        self.url = url
        self.logger = setup_logger()
        self.error_handler = UnifiedErrorHandler("BitgetWebSocket")
        self.is_connected = False
        self.subscriptions = {}
        self.ping_task = None
        
    async def connect(self) -> bool:
        """Подключение к WebSocket"""
        try:
            self.logger.info(f"Подключение к Bitget WebSocket: {self.url}")
            
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self.websocket = await websockets.connect(self.url, ssl=ssl_context)
            
            self.is_connected = True

            self.ping_task = asyncio.create_task(self._send_ping())
            
            self.logger.info("WebSocket подключение установлено")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorType.NETWORK_ERROR,
                {
                    "operation": "websocket_connect",
                    "url": self.url
                }
            )
            self.logger.error(f"Ошибка подключения WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Отключение от WebSocket"""
        self.is_connected = False

        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
        
        self.subscriptions.clear()
        self.logger.info("WebSocket отключен")
    
    async def subscribe_ticker(self, symbol: str, callback: Callable) -> bool:
        """ Подписка на ticker канал для символа """
        if not self.is_connected:
            self.logger.error("WebSocket не подключен")
            # Use unified error handler
            self.error_handler.handle_error(
                Exception("WebSocket not connected"),
                ErrorType.VALIDATION_ERROR,
                {
                    "operation": "subscribe_ticker",
                    "symbol": symbol,
                    "reason": "websocket_not_connected"
                }
            )
            return False
        
        subscription_message = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "USDT-FUTURES",
                    "channel": "ticker",
                    "instId": symbol.upper()
                }
            ]
        }
        
        try:
            await self.websocket.send(json.dumps(subscription_message))
            self.subscriptions[symbol] = callback
            self.logger.info(f"Подписка на ticker {symbol}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorType.NETWORK_ERROR,
                {
                    "operation": "subscribe_ticker",
                    "symbol": symbol
                }
            )
            self.logger.error(f"Ошибка подписки на {symbol}: {e}")
            return False
    
    async def unsubscribe_ticker(self, symbol: str) -> bool:
        """ Отписка от ticker канала """
        if not self.is_connected:
            return False
        
        unsubscription_message = {
            "op": "unsubscribe",
            "args": [
                {
                    "instType": "USDT-FUTURES",
                    "channel": "ticker",
                    "instId": symbol.upper()
                }
            ]
        }
        
        try:
            await self.websocket.send(json.dumps(unsubscription_message))
            self.subscriptions.pop(symbol, None)
            self.logger.info(f"Отписка от ticker {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка отписки от {symbol}: {e}")
            return False
    
    def get_subscribed_symbols(self) -> list:
        """Возвращает список символов с активными подписками"""
        return list(self.subscriptions.keys())
    
    async def listen(self):
        """Основной цикл прослушивания WebSocket сообщений"""
        while self.is_connected:
            try:
                message_str = await self.websocket.recv()
                message = json.loads(message_str)

                if "data" in message and message.get("arg", {}).get("channel") == "ticker":
                    await self._handle_ticker_data(message)

                elif "event" in message and message["event"] == "error":
                    await self._handle_subscription_error(message)

                elif "event" in message and message["event"] == "subscribe":
                    await self._handle_subscription_success(message)
                
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket соединение закрыто")
                self.error_handler.handle_error(
                    Exception("WebSocket connection closed"),
                    ErrorType.NETWORK_ERROR,
                    {
                        "operation": "websocket_listen",
                        "reason": "connection_closed"
                    }
                )
                self.is_connected = False
                break
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Ошибка парсинга JSON: {e}")
                self.error_handler.handle_error(
                    e,
                    ErrorType.API_ERROR,
                    {
                        "operation": "websocket_listen",
                        "reason": "json_decode_error"
                    }
                )
                
            except asyncio.CancelledError:
                self.error_handler.handle_error(
                    Exception("Listen task cancelled"),
                    ErrorType.SYSTEM_ERROR,
                    {
                        "operation": "websocket_listen",
                        "reason": "task_cancelled"
                    }
                )
                break
                
            except Exception as e:
                self.logger.error(f"Ошибка в listen(): {e}")
                self.error_handler.handle_error(
                    e,
                    ErrorType.UNKNOWN_ERROR,
                    {
                        "operation": "websocket_listen",
                        "reason": "unexpected_error"
                    }
                )
                await asyncio.sleep(1)
    
    async def _handle_ticker_data(self, message: Dict):
        """Обработка данных тикера - упрощенная версия"""
        try:
            arg = message.get("arg", {})
            inst_id = arg.get("instId")
            
            if not inst_id or inst_id not in self.subscriptions:
                return
            
            data_list = message.get("data", [])
            if not data_list:
                return

            ticker_raw = data_list[0]

            ticker_data = {
                "symbol": ticker_raw.get("instId"),
                "last_price": float(ticker_raw.get("lastPr", 0)),
                "mark_price": float(ticker_raw.get("markPrice", 0))
            }

            callback = self.subscriptions[inst_id]
            await callback(ticker_data)
                
        except Exception as e:
            self.logger.error(f"Ошибка обработки ticker данных: {e}")
    
    async def _handle_subscription_error(self, message: Dict):
        """Обработка ошибок подписки"""
        code = message.get("code")
        msg = message.get("msg", "Неизвестная ошибка")
        arg = message.get("arg", {})
        inst_id = arg.get("instId")
        
        self.logger.error(f"Ошибка подписки на {inst_id}: код {code} - {msg}")
    
    async def _handle_subscription_success(self, message: Dict):
        """Обработка успешной подписки"""
        arg = message.get("arg", {})
        inst_id = arg.get("instId")
        
        self.logger.info(f"Подписка успешна: {inst_id}")
    
    async def _send_ping(self):
        """Периодическая отправка ping для поддержания соединения"""
        while self.is_connected:
            try:
                # Отправляем ping каждые 20 секунд
                await asyncio.sleep(20)
                
                if self.is_connected and self.websocket:
                    await self.websocket.ping()
                    self.logger.debug("Отправлен WebSocket ping")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Ошибка отправки ping: {e}")
                await asyncio.sleep(5)
