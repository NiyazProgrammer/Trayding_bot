"""
Модуль проверок безопасности для торговых операций

Обеспечивает:
1. Проверку разумности цен (нельзя менять цену слишком далеко от рынка)
2. Проверку объемов (нельзя ставить объём больше позиции)
3. Логирование каждого изменения
4. Отмену действия при любых подозрительных параметрах
"""

from typing import Dict, List, Tuple, Optional
from utils.logging_setup import setup_logger


class SafetyValidator:
    """Валидатор безопасности для торговых операций"""
    
    # Константы безопасности
    MAX_PRICE_DEVIATION_PERCENT = 0.20  # Максимальное отклонение цены от рынка: 20%
    MAX_STOP_LOSS_DISTANCE_PERCENT = 0.15  # Максимальное расстояние SL от текущей цены: 15%
    MIN_STOP_LOSS_DISTANCE_PERCENT = 0.005  # Минимальное расстояние SL от текущей цены: 0.5%
    MAX_TAKE_PROFIT_DISTANCE_PERCENT = 0.50  # Максимальное расстояние TP: 50%
    
    def __init__(self, exchange_connector):
        """
        Args:
            exchange_connector: Коннектор к бирже для получения текущих цен
        """
        self.exchange = exchange_connector
        self.logger = setup_logger()
    
    def validate_price(
        self,
        symbol: str,
        price: float,
        price_type: str,  # "stop_loss", "take_profit", "limit", "trigger"
        side: Optional[str] = None,  # "long" или "short" (для SL/TP)
        current_price: Optional[float] = None
    ) -> Dict:
        """
        Проверка разумности цены - нельзя менять цену слишком далеко от рынка
        """
        errors = []
        warnings = []
        
        try:
            if current_price is None:
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = float(ticker["last"])
            
            # Цена должна быть положительной
            if price <= 0:
                errors.append(f"Цена должна быть положительной (получено: ${price})")
                return {
                    "valid": False,
                    "errors": errors,
                    "warnings": warnings,
                    "current_price": current_price,
                    "deviation_percent": 0
                }
            
            # Цена не должна быть слишком далеко от рынка
            deviation = abs(price - current_price) / current_price
            
            if price_type == "stop_loss":

                if side == "long" and price >= current_price:
                    errors.append(
                        f"Стоп-лосс для LONG должен быть НИЖЕ текущей цены:\n"
                        f"   SL: ${price:,.4f} >= текущая: ${current_price:,.4f}"
                    )
                elif side == "short" and price <= current_price:
                    errors.append(
                        f"Стоп-лосс для SHORT должен быть ВЫШЕ текущей цены:\n"
                        f"   SL: ${price:,.4f} <= текущая: ${current_price:,.4f}"
                    )
                
                if deviation > self.MAX_STOP_LOSS_DISTANCE_PERCENT:
                    errors.append(
                        f"Стоп-лосс слишком далеко от рынка:\n"
                        f"   Расстояние: {deviation:.2%} > максимум {self.MAX_STOP_LOSS_DISTANCE_PERCENT:.2%}\n"
                        f"   SL: ${price:,.4f}, текущая: ${current_price:,.4f}"
                    )
                
                if deviation < self.MIN_STOP_LOSS_DISTANCE_PERCENT:
                    warnings.append(
                        f"Стоп-лосс слишком близко к рынку (риск немедленной активации):\n"
                        f"   Расстояние: {deviation:.2%} < минимум {self.MIN_STOP_LOSS_DISTANCE_PERCENT:.2%}"
                    )
            
            elif price_type == "take_profit":

                if side == "long" and price <= current_price:
                    warnings.append(
                        f"Тейк-профит для LONG обычно ВЫШЕ текущей цены:\n"
                        f"   TP: ${price:,.4f} <= текущая: ${current_price:,.4f}"
                    )
                elif side == "short" and price >= current_price:
                    warnings.append(
                        f"Тейк-профит для SHORT обычно НИЖЕ текущей цены:\n"
                        f"   TP: ${price:,.4f} >= текущая: ${current_price:,.4f}"
                    )
                
                if deviation > self.MAX_TAKE_PROFIT_DISTANCE_PERCENT:
                    warnings.append(
                        f"Тейк-профит далеко от рынка (может не сработать):\n"
                        f"   Расстояние: {deviation:.2%} > {self.MAX_TAKE_PROFIT_DISTANCE_PERCENT:.2%}"
                    )
            
            else:
                # Для других типов цен (limit, trigger) - общая проверка
                if deviation > self.MAX_PRICE_DEVIATION_PERCENT:
                    errors.append(
                        f"Цена слишком далеко от рынка:\n"
                        f"   Отклонение: {deviation:.2%} > максимум {self.MAX_PRICE_DEVIATION_PERCENT:.2%}\n"
                        f"   Цена: ${price:,.4f}, текущая: ${current_price:,.4f}"
                    )
            
            # Защита от очевидных опечаток
            if price < 0.01:
                errors.append(
                    f"Цена подозрительно низкая (возможна опечатка): ${price}"
                )
            
            if errors:
                self.logger.error(
                    f"Проверка цены FAILED для {symbol}:\n"
                    f"   Тип: {price_type}, Цена: ${price:,.4f}, Текущая: ${current_price:,.4f}\n"
                    f"   Ошибки: {'; '.join(errors)}"
                )
            elif warnings:
                self.logger.warning(
                    f"Проверка цены с предупреждениями для {symbol}:\n"
                    f"   Тип: {price_type}, Цена: ${price:,.4f}, Текущая: ${current_price:,.4f}\n"
                    f"   Предупреждения: {'; '.join(warnings)}"
                )
            else:
                self.logger.debug(
                    f"Проверка цены OK для {symbol}: "
                    f"{price_type} ${price:,.4f} (текущая: ${current_price:,.4f})"
                )
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "current_price": current_price,
                "deviation_percent": deviation
            }
            
        except Exception as e:
            error_msg = f"Ошибка при проверке цены для {symbol}: {e}"
            self.logger.error(error_msg)
            return {
                "valid": False,
                "errors": [error_msg],
                "warnings": [],
                "current_price": 0,
                "deviation_percent": 0
            }
    
    def validate_order_size(
        self,
        symbol: str,
        order_size: float,
        side: str,  # "buy" или "sell"
        position_size: Optional[float] = None,
        max_position_size: Optional[float] = None
    ) -> Dict:
        """
        Проверка размера ордера - нельзя ставить объём больше позиции
        """
        errors = []
        warnings = []
        
        try:
            if order_size <= 0:
                errors.append(f"Размер ордера должен быть положительным (получено: {order_size})")
                return {
                    "valid": False,
                    "errors": errors,
                    "warnings": warnings,
                    "position_size": position_size or 0,
                    "order_size": order_size
                }
            
            # Для закрывающих ордеров (SL/TP) - размер не больше позиции
            if position_size is not None and position_size > 0:
                if order_size > position_size:
                    errors.append(
                        f"Размер ордера больше позиции:\n"
                        f"   Ордер: {order_size} > Позиция: {position_size}\n"
                        f"   Это может привести к открытию обратной позиции!"
                    )
                
                # Предупреждение если ордер закрывает не всю позицию
                if order_size < position_size * 0.95:  # Меньше 95% позиции
                    warnings.append(
                        f"Ордер закрывает только часть позиции:\n"
                        f"   Ордер: {order_size} ({order_size/position_size:.1%} от позиции)\n"
                        f"   Позиция: {position_size}"
                    )
            
            if max_position_size is not None and order_size > max_position_size:
                errors.append(
                    f"Размер ордера превышает максимум:\n"
                    f"   Ордер: {order_size} > Максимум: {max_position_size}"
                )
            
            if errors:
                self.logger.error(
                    f"Проверка размера FAILED для {symbol}:\n"
                    f"   Размер ордера: {order_size}, Позиция: {position_size}\n"
                    f"   Ошибки: {'; '.join(errors)}"
                )
            elif warnings:
                self.logger.warning(
                    f" Проверка размера с предупреждениями для {symbol}:\n"
                    f"   Размер ордера: {order_size}, Позиция: {position_size}\n"
                    f"   Предупреждения: {'; '.join(warnings)}"
                )
            else:
                self.logger.debug(
                    f" Проверка размера OK для {symbol}: {order_size}"
                )
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "position_size": position_size or 0,
                "order_size": order_size
            }
            
        except Exception as e:
            error_msg = f"Ошибка при проверке размера для {symbol}: {e}"
            self.logger.error(error_msg)
            return {
                "valid": False,
                "errors": [error_msg],
                "warnings": [],
                "position_size": 0,
                "order_size": order_size
            }
    
    def validate_stop_loss_order(
        self,
        symbol: str,
        stop_loss_price: float,
        position_side: str,  # "long" или "short"
        position_size: float,
        order_size: Optional[float] = None,
        entry_price: Optional[float] = None
    ) -> Dict:
        """
        Комплексная проверка стоп-лосс ордера
        
        Проверяет:
        1. Разумность цены стоп-лосса
        2. Размер ордера относительно позиции
        3. Расстояние от точки входа (если известна)
        """
        all_errors = []
        all_warnings = []
        
        # Если размер ордера не указан, используем размер позиции
        if order_size is None:
            order_size = position_size
        
        #  Валидация цены
        price_validation = self.validate_price(
            symbol=symbol,
            price=stop_loss_price,
            price_type="stop_loss",
            side=position_side
        )
        
        all_errors.extend(price_validation["errors"])
        all_warnings.extend(price_validation["warnings"])
        current_price = price_validation["current_price"]
        
        # Валидация размера
        size_validation = self.validate_order_size(
            symbol=symbol,
            order_size=order_size,
            side="sell" if position_side == "long" else "buy",
            position_size=position_size
        )
        
        all_errors.extend(size_validation["errors"])
        all_warnings.extend(size_validation["warnings"])
        
        # Расстояние от точки входа (если известна)
        if entry_price and entry_price > 0:
            if position_side == "long":
                loss_percent = (entry_price - stop_loss_price) / entry_price
            else:  # short
                loss_percent = (stop_loss_price - entry_price) / entry_price
            
            if loss_percent > 0.20:  # Больше 20% убытка
                all_warnings.append(
                    f"Стоп-лосс далеко от точки входа (убыток {loss_percent:.1%}):\n"
                    f"   Entry: ${entry_price:,.4f}, SL: ${stop_loss_price:,.4f}"
                )
            
            if loss_percent < 0:  # SL в прибыльной зоне
                all_warnings.append(
                    f"Стоп-лосс в прибыльной зоне (break-even/trailing):\n"
                    f"   Entry: ${entry_price:,.4f}, SL: ${stop_loss_price:,.4f}, Прибыль: {abs(loss_percent):.1%}"
                )
        
        result = {
            "valid": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "current_price": current_price,
            "position_size": position_size,
            "order_size": order_size,
            "stop_loss_price": stop_loss_price
        }
        
        if all_errors:
            self.logger.error(
                f" Валидация стоп-лосса FAILED для {symbol}:\n"
                f"   SL: ${stop_loss_price:,.4f}, Позиция: {position_side} {position_size}\n"
                f"   ОШИБКИ:\n" + "\n".join(f"      {e}" for e in all_errors)
            )
        elif all_warnings:
            self.logger.warning(
                f" Валидация стоп-лосса с предупреждениями для {symbol}:\n"
                f"   SL: ${stop_loss_price:,.4f}, Позиция: {position_side} {position_size}\n"
                f"   ПРЕДУПРЕЖДЕНИЯ:\n" + "\n".join(f"      {w}" for w in all_warnings)
            )
        else:
            self.logger.info(
                f" Валидация стоп-лосса OK для {symbol}: "
                f"{position_side} ${stop_loss_price:,.4f} (размер: {order_size})"
            )
        
        return result
    
    def log_operation(
        self,
        operation_type: str,
        symbol: str,
        params: Dict,
        validation_result: Dict,
        executed: bool = False
    ):
        """
        Логирование каждого изменения
        """
        status = " EXECUTED" if executed else "REJECTED"
        
        log_entry = (
            f"{status} | {operation_type.upper()} | {symbol}\n"
            f"Параметры:\n"
        )
        
        for key, value in params.items():
            log_entry += f"  • {key}: {value}\n"
        
        if validation_result.get("errors"):
            log_entry += f"\nОШИБКИ ВАЛИДАЦИИ:\n"
            for error in validation_result["errors"]:
                log_entry += f"  {error}\n"
        
        if validation_result.get("warnings"):
            log_entry += f"\n️ ПРЕДУПРЕЖДЕНИЯ:\n"
            for warning in validation_result["warnings"]:
                log_entry += f"  {warning}\n"
        
        log_entry += f"{'='*80}\n"
        
        if executed:
            self.logger.info(log_entry)
        else:
            self.logger.error(log_entry)

