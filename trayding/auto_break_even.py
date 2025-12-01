import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
from utils.logging_setup import setup_logger
from api.bitget_websocket import BitgetWebSocketClient


class AutoBreakEvenSystem:
    """ Автоматическая система перевода позиций в безубыток """
    
    def __init__(self, position_manager):
        self.position_manager = position_manager
        self.logger = setup_logger()

        self.ws_client = BitgetWebSocketClient()

        self.monitored_positions = {}  # {symbol: config}

        self.is_active = False
        self.monitoring_task = None

        self.stats = {
            "price_updates": 0,
            "break_even_checks": 0,
            "break_even_activated": 0,
            "positions_added": 0,
            "positions_removed": 0,
            "errors": 0,
            "started_at": None
        }
    
    async def start_system(self) -> bool:
        """ Запуск системы автоматического break-even """
        if self.is_active:
            self.logger.warning("Система break-even уже активна")
            return True
        
        try:
            if not await self.ws_client.connect():
                self.logger.error("Не удалось подключиться к WebSocket")
                return False

            self.monitoring_task = asyncio.create_task(self.ws_client.listen())
            
            self.is_active = True
            self.stats["started_at"] = time.time()
            
            self.logger.info("Система автоматического break-even запущена")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска системы break-even: {e}")
            return False
    
    async def stop_system(self):
        """Остановка системы break-even"""
        if not self.is_active:
            return
        
        self.is_active = False
        
        # Останавливаем мониторинг
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Отключаемся от WebSocket
        await self.ws_client.disconnect()
        
        self.monitored_positions.clear()
        
        self.logger.info("Система автоматического break-even остановлена")
    
    async def add_position(
        self,
        symbol: str,
        profit_threshold: float = 0.03,
        buffer_percent: float = 0.001,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> bool:
        """Добавить позицию в систему break-even мониторинга"""
        if not self.is_active:
            self.logger.error("Система break-even не активна")
            return False

        positions = self.position_manager.get_current_positions(
            symbol=symbol,
            product_type=product_type,
            margin_coin=margin_coin
        )
        
        if not positions:
            self.logger.warning(f"Нет открытых позиций для {symbol}")
            return False

        active_positions = []
        for pos in positions:
            size = float(pos.get("size", pos.get("total", 0)))
            if size != 0:
                active_positions.append(pos)
        
        if not active_positions:
            self.logger.warning(f"Нет активных позиций для {symbol}")
            return False

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

        success = await self.ws_client.subscribe_ticker(
            symbol, 
            self._create_price_handler(symbol)
        )
        
        if success:
            self.stats["positions_added"] += 1
            self.logger.info(
                f"Добавлен в break-even мониторинг: {symbol} "
                f"(порог: {profit_threshold:.1%}, буфер: {buffer_percent:.3%})"
            )
            return True
        else:
            self.monitored_positions.pop(symbol, None)
            self.logger.error(f"Не удалось подписаться на {symbol}")
            return False
    
    async def remove_position(self, symbol: str) -> bool:
        """Удалить позицию из break-even мониторинга"""
        if symbol not in self.monitored_positions:
            self.logger.warning(f"Позиция {symbol} не отслеживается")
            return False

        await self.ws_client.unsubscribe_ticker(symbol)

        del self.monitored_positions[symbol]
        self.stats["positions_removed"] += 1
        
        self.logger.info(f"Удален из break-even мониторинга: {symbol}")
        return True
    
    def _create_price_handler(self, symbol: str):
        """Создает обработчик цен для конкретного символа"""
        
        async def price_handler(ticker_data):
            """Обработчик обновлений цен для break-even проверки"""
            try:
                current_price = ticker_data["last_price"]
                
                if symbol not in self.monitored_positions:
                    return
                
                self.stats["price_updates"] += 1
                config = self.monitored_positions[symbol]
                
                # Проверяем, не активирован ли уже break-even
                if config.get("break_even_activated"):
                    return
                
                # Ограничиваем частоту проверок (не чаще раза в 2 секунды)
                current_time = time.time()
                if current_time - config["last_check"] < 2.0:
                    return
                
                config["last_check"] = current_time
                self.stats["break_even_checks"] += 1

                result = self.position_manager.auto_break_even(
                    symbol=symbol,
                    profit_threshold=config["profit_threshold"],
                    buffer_percent=config["buffer_percent"],
                    product_type=config["product_type"],
                    margin_coin=config["margin_coin"]
                )

                if result.get("success") and result.get("break_even_activated", 0) > 0:
                    config["break_even_activated"] = True
                    config["activation_price"] = current_price
                    config["activation_time"] = current_time
                    
                    self.stats["break_even_activated"] += result["break_even_activated"]

                    await self._notify_break_even_activation(symbol, result, current_price)

                    await self.remove_position(symbol)
                
                elif result.get("waiting_for_profit", 0) > 0:
                    # Позиция есть, но прибыль недостаточна продолжаем мониторинг
                    pass
                
                elif result.get("errors", 0) > 0:
                    self.stats["errors"] += result["errors"]
                    self.logger.warning(f"Ошибки при проверке break-even для {symbol}")
                
            except Exception as e:
                self.logger.error(f"Ошибка в обработчике цен для {symbol}: {e}")
                self.stats["errors"] += 1
        
        return price_handler
    
    async def _notify_break_even_activation(self, symbol: str, result: Dict, current_price: float):
        """Отправка уведомления о активации break-even"""
        try:
            details = result.get("details", [])
            successful_details = [d for d in details if d.get("status") == "success"]

            self.logger.info(
                f"Break-even активирован для {symbol} @ {current_price:.4f}, "
                f"обновлено позиций: {len(successful_details)}"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            for detail in successful_details:
                self.logger.debug(
                    f"${detail.get('position_side', '').upper()}: "
                    f"entry=${detail.get('entry_price', 0):.4f} → "
                    f"SL=${detail.get('new_stop_loss', 0):.4f} "
                    f"action={detail.get('action', 'unknown')} "
                    f"(прибыль: {detail.get('profit_percent', 0):.2%})"
                )
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления: {e}")
    
    async def add_all_positions(
        self,
        profit_threshold: float = 0.03,
        buffer_percent: float = 0.001,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> Dict:
        """Добавить все активные позиции в break-even мониторинг"""
        if not self.is_active:
            return {"success": False, "message": "Система не активна"}

        all_positions = self.position_manager.get_current_positions(
            product_type=product_type,
            margin_coin=margin_coin
        )
        
        if not all_positions:
            return {"success": False, "message": "Нет открытых позиций"}

        symbols = []
        for pos in all_positions:
            size = float(pos.get("size", pos.get("total", 0)))
            if size != 0:
                symbols.append(pos.get("symbol"))
        symbols = list(set(symbols))
        
        if not symbols:
            return {"success": False, "message": "Нет активных позиций"}

        results = []
        successful_additions = 0
        
        for symbol in symbols:
            success = await self.add_position(
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
            f"Добавлено в break-even мониторинг: {successful_additions}/{len(symbols)} символов"
        )
        
        return {
            "success": successful_additions > 0,
            "total_symbols": len(symbols),
            "successful_additions": successful_additions,
            "results": results,
            "message": f"Добавлено {successful_additions} из {len(symbols)} символов в break-even мониторинг"
        }
    
    def get_system_status(self) -> Dict:
        """Получить статус системы break-even"""
        uptime = 0
        if self.stats["started_at"]:
            uptime = time.time() - self.stats["started_at"]
        
        monitored_symbols = list(self.monitored_positions.keys())
        
        return {
            "is_active": self.is_active,
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
                    "monitoring_duration": time.time() - config["added_at"],
                    "last_check": datetime.fromtimestamp(config["last_check"]).strftime("%H:%M:%S") if config["last_check"] > 0 else "Never"
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
    
    def print_status(self):
        """Красивый вывод статуса системы в консоль"""
        status = self.get_system_status()
        
        print(f"СТАТУС СИСТЕМЫ BREAK-EVEN")
        print(f"Система: {'Активна' if status['is_active'] else 'Неактивна'} | "
              f"WS: {'Подключен' if status['websocket_connected'] else 'Отключен'} | "
              f"Uptime: {status['uptime_formatted']} | "
              f"Символов: {status['monitored_count']}")
        
        stats = status["statistics"]
        print(f"\nСТАТИСТИКА:")
        print(f"Обновлений цен: {stats['price_updates']}")
        print(f"Проверок break-even: {stats['break_even_checks']}")
        print(f"Активировано break-even: {stats['break_even_activated']}")
        print(f"Позиций добавлено: {stats['positions_added']}")
        print(f"Позиций удалено: {stats['positions_removed']}")
        print(f"Ошибок: {stats['errors']}")
        
        if status["monitored_symbols"]:
            print(f"ОТСЛЕЖИВАЕМЫЕ ПОЗИЦИИ:")
            for symbol, details in status["positions_details"].items():
                activated = "Активирован" if details["break_even_activated"] else "Мониторинг"
                duration = self._format_duration(details["monitoring_duration"])
                
                print(f"      {symbol}:")
                print(f"Порог: {details['profit_threshold']}")
                print(f"Буфер: {details['buffer_percent']}")
                print(f"Статус: {activated}")
                print(f"Длительность: {duration}")
                print(f"Последняя проверка: {details['last_check']}")
        else:
            print(f"Нет позиций в мониторинге")
    
    async def __aenter__(self):
        """Поддержка async context manager"""
        await self.start_system()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие при выходе из контекста"""
        await self.stop_system()
