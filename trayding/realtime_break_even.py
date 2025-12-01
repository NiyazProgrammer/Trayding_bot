import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
from utils.logging_setup import setup_logger
from api.bitget_websocket import BitgetWebSocketClient


class RealtimeBreakEvenManager:
    
    def __init__(self, position_manager):
        """
        Инициализация менеджера
        
        Args:
            position_manager: Экземпляр PositionManager
        """
        self.position_manager = position_manager
        self.logger = setup_logger()
        
        # WebSocket клиент
        self.ws_client = BitgetWebSocketClient()
        
        # Отслеживаемые позиции
        self.monitored_positions = {}  # {symbol: position_config}
        
        # Статистика
        self.stats = {
            "price_updates": 0,
            "break_even_checks": 0,
            "break_even_activated": 0,
            "errors": 0,
            "started_at": None
        }
        
        # Состояние
        self.is_monitoring = False
        self.monitoring_task = None
    
    async def start_monitoring(self) -> bool:
        """
        Запуск real-time мониторинга break-even
        """
        if self.is_monitoring:
            self.logger.warning("Мониторинг уже запущен")
            return True
        
        try:
            # Подключаемся к WebSocket
            if not await self.ws_client.connect():
                self.logger.error("Не удалось подключиться к WebSocket")
                return False
            
            # Запускаем задачу мониторинга
            self.monitoring_task = asyncio.create_task(self.ws_client.listen())
            
            self.is_monitoring = True
            self.stats["started_at"] = time.time()
            
            self.logger.info("Real-time break-even мониторинг запущен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска мониторинга: {e}")
            return False
    
    async def stop_monitoring(self):
        """Остановка мониторинга"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        # Останавливаем задачу мониторинга
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Отключаемся от WebSocket
        await self.ws_client.disconnect()
        
        # Очищаем отслеживаемые позиции
        self.monitored_positions.clear()
        
        self.logger.info("Real-time break-even мониторинг остановлен")
    
    async def add_position_monitoring(
        self,
        symbol: str,
        profit_threshold: float = 0.03,
        buffer_percent: float = 0.001,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> bool:
        """
        Добавить позицию в real-time мониторинг break-even
        """
        if not self.is_monitoring:
            self.logger.error("Мониторинг не запущен")
            return False
        
        # Проверяем, есть ли активные позиции для этого символа
        positions = self.position_manager.get_current_positions(
            symbol=symbol,
            product_type=product_type,
            margin_coin=margin_coin
        )
        
        active_positions = []
        for pos in positions:
            size_field = float(pos.get("size", pos.get("total", 0)))
            if size_field != 0:
                active_positions.append(pos)
        
        if not active_positions:
            self.logger.warning(f"Нет активных позиций для {symbol}")
            return False
        
        # Сохраняем конфигурацию мониторинга
        self.monitored_positions[symbol] = {
            "profit_threshold": profit_threshold,
            "buffer_percent": buffer_percent,
            "product_type": product_type,
            "margin_coin": margin_coin,
            "positions": active_positions,
            "last_check": 0,
            "break_even_activated": False,
            "added_at": time.time()
        }
        
        # Подписываемся на ticker этого символа
        success = await self.ws_client.subscribe_ticker(
            symbol, 
            lambda ticker_data: asyncio.create_task(
                self._on_price_update(ticker_data)
            )
        )
        
        if success:
            self.logger.info(
                f"Добавлен в мониторинг: {symbol} "
                f"(порог: {profit_threshold:.1%}, буфер: {buffer_percent:.3%})"
            )
            return True
        else:
            # Удаляем из мониторинга если подписка не удалась
            self.monitored_positions.pop(symbol, None)
            return False
    
    async def remove_position_monitoring(self, symbol: str) -> bool:
        """
        Удалить позицию из мониторинга
        """
        if symbol not in self.monitored_positions:
            self.logger.warning(f"Позиция {symbol} не отслеживается")
            return False
        
        # Отписываемся от ticker
        await self.ws_client.unsubscribe_ticker(symbol)
        
        # Удаляем из мониторинга
        del self.monitored_positions[symbol]
        
        self.logger.info(f"Удален из мониторинга: {symbol}")
        return True
    
    async def _on_price_update(self, ticker_data: Dict):
        """
        Обработчик обновлений цен от WebSocket
        """
        try:
            symbol = ticker_data["symbol"]
            current_price = ticker_data["last_price"]
            
            if symbol not in self.monitored_positions:
                return
            
            self.stats["price_updates"] += 1
            
            config = self.monitored_positions[symbol]
            
            # Проверяем, не активирован ли уже break-even
            if config.get("break_even_activated"):
                return
            
            # Ограничиваем частоту проверок (не чаще раза в секунду)
            current_time = time.time()
            if current_time - config["last_check"] < 1.0:
                return
            
            config["last_check"] = current_time
            self.stats["break_even_checks"] += 1
            
            self.logger.debug(
                f"{symbol}: цена ${current_price:,.4f}, проверка break-even..."
            )

            
            # Вызываем auto_break_even
            result = self.position_manager.auto_break_even(
                symbol=symbol,
                profit_threshold=config["profit_threshold"],
                buffer_percent=config["buffer_percent"],
                product_type=config["product_type"],
                margin_coin=config["margin_coin"]
            )
            
            # Обрабатываем результат
            if result.get("success") and result.get("break_even_activated", 0) > 0:
                config["break_even_activated"] = True
                self.stats["break_even_activated"] += result["break_even_activated"]
                
                self.logger.info(
                    f"BREAK-EVEN АКТИВИРОВАН! {symbol}: "
                    f"активировано {result['break_even_activated']} позиций при цене ${current_price:,.4f}"
                )
                
                await self._send_break_even_notification(symbol, result, current_price)
                
                # Удаляем из мониторинга (break-even уже активирован)
                await self.remove_position_monitoring(symbol)
            
            elif result.get("errors", 0) > 0:
                self.stats["errors"] += result["errors"]
                self.logger.warning(f"Ошибки при проверке break-even для {symbol}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки обновления цены для {ticker_data.get('symbol', 'unknown')}: {e}")
            self.stats["errors"] += 1
    
    async def _send_break_even_notification(self, symbol: str, result: Dict, current_price: float):
        """Отправка уведомления о активации break-even"""
        try:
            details = result.get("details", [])
            successful_details = [d for d in details if d.get("status") == "success"]
            
            notification = f"BREAK-EVEN АКТИВИРОВАН!\n"
            notification += f"Символ: {symbol}\n"
            notification += f"Цена: ${current_price:,.4f}\n"
            notification += f"Позиций обновлено: {len(successful_details)}\n"
            
            for detail in successful_details:
                side = detail.get("position_side", "").upper()
                new_sl = detail.get("new_stop_loss", 0)
                action = detail.get("action", "unknown")
                notification += f"   • {side}: SL {action} → ${new_sl:.4f}\n"
            
            notification += f"Время: {datetime.now().strftime('%H:%M:%S')}"
            
            # Выводим в консоль (можно расширить для отправки в Telegram)
            self.logger.info(f"\n{notification}\n")
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления: {e}")
    
    async def add_all_positions_monitoring(
        self,
        profit_threshold: float = 0.03,
        buffer_percent: float = 0.001,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> Dict:
        """
        Добавить все активные позиции в мониторинг
        """
        if not self.is_monitoring:
            return {"success": False, "message": "Мониторинг не запущен"}
        
        # Получаем все активные позиции
        all_positions = self.position_manager.get_current_positions(
            product_type=product_type,
            margin_coin=margin_coin
        )
        
        if not all_positions:
            return {"success": False, "message": "Нет открытых позиций"}
        
        # Получаем уникальные символы с активными позициями
        symbols = []
        for pos in all_positions:
            size_field = float(pos.get("size", pos.get("total", 0)))
            if size_field != 0:
                symbols.append(pos.get("symbol"))
        symbols = list(set(symbols))
        
        if not symbols:
            return {"success": False, "message": "Нет активных позиций"}
        
        # Добавляем каждый символ в мониторинг
        results = []
        successful_additions = 0
        
        for symbol in symbols:
            success = await self.add_position_monitoring(
                symbol=symbol,
                profit_threshold=profit_threshold,
                buffer_percent=buffer_percent,
                product_type=product_type,
                margin_coin=margin_coin
            )
            
            results.append({
                "symbol": symbol,
                "success": success
            })
            
            if success:
                successful_additions += 1
        
        self.logger.info(
            f"Добавлено в мониторинг: {successful_additions}/{len(symbols)} символов"
        )
        
        return {
            "success": successful_additions > 0,
            "total_symbols": len(symbols),
            "successful_additions": successful_additions,
            "results": results,
            "message": f"Добавлено {successful_additions} из {len(symbols)} символов"
        }
    
    def get_monitoring_status(self) -> Dict:
        """
        Получить статус мониторинга
        
        Returns:
            dict: Подробная информация о состоянии мониторинга
        """
        uptime = 0
        if self.stats["started_at"]:
            uptime = time.time() - self.stats["started_at"]
        
        monitored_symbols = list(self.monitored_positions.keys())
        
        return {
            "is_monitoring": self.is_monitoring,
            "websocket_connected": self.ws_client.is_connected,
            "monitored_symbols": monitored_symbols,
            "monitored_count": len(monitored_symbols),
            "uptime_seconds": uptime,
            "uptime_formatted": self._format_duration(uptime),
            "statistics": self.stats.copy(),
            "positions_details": {
                symbol: {
                    "profit_threshold": f"{config['profit_threshold']:.1%}",
                    "buffer_percent": f"{config['buffer_percent']:.3%}",
                    "break_even_activated": config["break_even_activated"],
                    "monitoring_duration": time.time() - config["added_at"]
                }
                for symbol, config in self.monitored_positions.items()
            }
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Форматирование длительности"""
        if seconds < 60:
            return f"{seconds:.0f}с"
        elif seconds < 3600:
            return f"{seconds/60:.0f}м {seconds%60:.0f}с"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}ч {minutes}м"
    
    async def __aenter__(self):
        """Поддержка async context manager"""
        await self.start_monitoring()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие при выходе из контекста"""
        await self.stop_monitoring()
