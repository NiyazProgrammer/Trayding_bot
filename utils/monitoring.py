import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional
from utils.logging_setup import setup_logger


class APIMonitor:
    """
    Мониторинг API-запросов
    
    Функции:
    - Сбор метрик по каждому запросу
    - Расчёт статистики (среднее время, процент ошибок)
    - Сохранение в файл каждые 5 минут
    - Обнаружение аномальной активности
    """
    
    # Пороги для обнаружения аномалий
    MAX_REQUESTS_PER_MINUTE = 60  # Максимум запросов в минуту
    MAX_ERROR_RATE = 0.20  # Максимум 20% ошибок
    MAX_LATENCY_MS = 5000  # Максимальная задержка 5 секунд
    
    def __init__(self, monitoring_file: str = "monitoring.json", save_interval: int = 300):
        """
        Args:
            monitoring_file: Путь к файлу для сохранения метрик
            save_interval: Интервал сохранения в секундах (по умолчанию 300 = 5 минут)
        """
        self.logger = setup_logger()
        self.monitoring_file = monitoring_file
        self.save_interval = save_interval
        
        # Метрики текущей сессии
        self.requests_count = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_latency_ms = 0
        self.latencies = []  # Список всех задержек для расчёта статистики
        self.errors_by_type = {}  # Счётчик ошибок по типам
        
        # Временные метки
        self.session_start = time.time()
        self.last_save_time = time.time()
        self.last_anomaly_check = time.time()
        
        # История для обнаружения аномалий
        self.recent_requests_timestamps = []  # Временные метки последних запросов
        self.anomalies_detected = 0
        
        self.logger.info("API Monitor инициализирован")
    
    def record_request(
        self,
        success: bool,
        latency_ms: float,
        error_type: str = None,
        endpoint: str = None
    ):
        """
        Записать метрики одного API запроса
        """
        current_time = time.time()
        
        self.requests_count += 1
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            
            if error_type:
                self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        
        # Записываем задержку
        self.total_latency_ms += latency_ms
        self.latencies.append(latency_ms)
        
        # Сохраняем временную метку для обнаружения аномалий
        self.recent_requests_timestamps.append(current_time)
        
        # Удаляем старые метки (старше 1 минуты)
        one_minute_ago = current_time - 60
        self.recent_requests_timestamps = [
            ts for ts in self.recent_requests_timestamps 
            if ts > one_minute_ago
        ]
        
        # Проверка аномальной активности
        self._check_anomalies()
        
        # Периодическое сохранение
        if current_time - self.last_save_time >= self.save_interval:
            self.save_metrics()
    
    def _check_anomalies(self):
        """Проверка на аномальную активность"""
        current_time = time.time()
        
        # Проверяем не чаще раза в 10 секунд
        if current_time - self.last_anomaly_check < 10:
            return
        
        self.last_anomaly_check = current_time
        
        anomalies = []
        
        # Слишком много запросов в минуту
        requests_per_minute = len(self.recent_requests_timestamps)
        if requests_per_minute > self.MAX_REQUESTS_PER_MINUTE:
            anomalies.append(
                f"Высокая частота запросов: {requests_per_minute}/мин "
                f"(лимит: {self.MAX_REQUESTS_PER_MINUTE}/мин)"
            )
        
        # Высокий процент ошибок
        if self.requests_count > 10:  # Минимум 10 запросов для статистики
            error_rate = self.failed_requests / self.requests_count
            if error_rate > self.MAX_ERROR_RATE:
                anomalies.append(
                    f"Высокий процент ошибок: {error_rate:.1%} "
                    f"(лимит: {self.MAX_ERROR_RATE:.1%})"
                )
        
        # Высокая задержка
        if self.latencies:
            avg_latency = sum(self.latencies[-10:]) / len(self.latencies[-10:])  # Среднее по последним 10
            if avg_latency > self.MAX_LATENCY_MS:
                anomalies.append(
                    f"Высокая задержка API: {avg_latency:.0f}мс "
                    f"(лимит: {self.MAX_LATENCY_MS}мс)"
                )
        
        if anomalies:
            self.anomalies_detected += 1
            
            self.logger.warning(
                f" Аномальная активность API (обнаружение #{self.anomalies_detected}):\n" +
                "\n".join(f"   • {a}" for a in anomalies)
            )
    
    def get_metrics(self) -> Dict:
        """
        Получить текущие метрики
        """
        session_duration = time.time() - self.session_start
        
        # Базовые метрики
        metrics = {
            "session_start": datetime.fromtimestamp(self.session_start).isoformat(),
            "session_duration_seconds": session_duration,
            "total_requests": self.requests_count,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.requests_count 
                if self.requests_count > 0 else 0
            ),
            "error_rate": (
                self.failed_requests / self.requests_count 
                if self.requests_count > 0 else 0
            ),
        }
        
        # Метрики задержки
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            metrics["latency"] = {
                "average_ms": self.total_latency_ms / len(self.latencies),
                "min_ms": min(self.latencies),
                "max_ms": max(self.latencies),
                "median_ms": sorted_latencies[len(sorted_latencies) // 2],
                "p95_ms": sorted_latencies[int(len(sorted_latencies) * 0.95)] if len(sorted_latencies) > 20 else sorted_latencies[-1],
                "p99_ms": sorted_latencies[int(len(sorted_latencies) * 0.99)] if len(sorted_latencies) > 100 else sorted_latencies[-1]
            }
        else:
            metrics["latency"] = {
                "average_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "median_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0
            }
        
        # Метрики частоты
        if session_duration > 0:
            metrics["requests_per_minute"] = (self.requests_count / session_duration) * 60
            metrics["requests_per_hour"] = (self.requests_count / session_duration) * 3600
        else:
            metrics["requests_per_minute"] = 0
            metrics["requests_per_hour"] = 0
        
        # Ошибки по типам
        metrics["errors_by_type"] = self.errors_by_type.copy()
        
        # Аномалии
        metrics["anomalies_detected"] = self.anomalies_detected
        metrics["current_requests_per_minute"] = len(self.recent_requests_timestamps)
        
        # Метаданные
        metrics["timestamp"] = datetime.now().isoformat()
        metrics["monitoring_active"] = True
        
        return metrics
    
    def save_metrics(self):
        """Сохранить метрики в файл"""
        try:
            metrics = self.get_metrics()
            
            # Создаём или обновляем файл
            monitoring_data = {}
            
            if os.path.exists(self.monitoring_file):
                try:
                    with open(self.monitoring_file, 'r') as f:
                        monitoring_data = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning("Не удалось прочитать monitoring.json, создаём новый")
                    monitoring_data = {}
            
            # Добавляем текущую сессию
            session_id = datetime.fromtimestamp(self.session_start).strftime("%Y%m%d_%H%M%S")
            
            if "sessions" not in monitoring_data:
                monitoring_data["sessions"] = {}
            
            monitoring_data["sessions"][session_id] = metrics
            monitoring_data["last_update"] = datetime.now().isoformat()
            
            # Сохраняем
            with open(self.monitoring_file, 'w') as f:
                json.dump(monitoring_data, f, indent=2)
            
            self.last_save_time = time.time()
            
            self.logger.info(
                f"Метрики сохранены в {self.monitoring_file}\n"
                f"   Запросов: {metrics['total_requests']}, "
                f"Успешно: {metrics['successful_requests']}, "
                f"Ошибок: {metrics['failed_requests']}"
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения метрик: {e}")
    
    def print_summary(self):
        metrics = self.get_metrics()
        
        print(f"\n{'='*80}")
        print("СВОДКА МОНИТОРИНГА API")
        print(f"{'='*80}")
        
        # Общая информация
        duration_minutes = metrics["session_duration_seconds"] / 60
        print(f"Длительность сессии: {duration_minutes:.1f} минут")
        print(f"Всего запросов: {metrics['total_requests']}")
        print(f"Успешных: {metrics['successful_requests']} ({metrics['success_rate']:.1%})")
        print(f"Ошибок: {metrics['failed_requests']} ({metrics['error_rate']:.1%})")
        
        # Частота
        print(f"\nЧАСТОТА:")
        print(f"   • Запросов в минуту: {metrics['requests_per_minute']:.1f}")
        print(f"   • Запросов в час: {metrics['requests_per_hour']:.0f}")
        print(f"   • Текущая частота: {metrics['current_requests_per_minute']} req/min")
        
        # Задержка
        latency = metrics["latency"]
        print(f"\n ЗАДЕРЖКА:")
        print(f"   • Средняя: {latency['average_ms']:.0f} мс")
        print(f"   • Минимум: {latency['min_ms']:.0f} мс")
        print(f"   • Максимум: {latency['max_ms']:.0f} мс")
        print(f"   • Медиана: {latency['median_ms']:.0f} мс")
        print(f"   • P95: {latency['p95_ms']:.0f} мс")
        print(f"   • P99: {latency['p99_ms']:.0f} мс")
        
        # Ошибки по типам
        if metrics["errors_by_type"]:
            print(f"\n ОШИБКИ ПО ТИПАМ:")
            for error_type, count in sorted(metrics["errors_by_type"].items(), key=lambda x: x[1], reverse=True):
                print(f"   • {error_type}: {count}")
        
        # Аномалии
        if metrics["anomalies_detected"] > 0:
            print(f"\nАНОМАЛИИ: {metrics['anomalies_detected']} обнаружено")
        
        print(f"{'='*80}\n")
    
    def reset_metrics(self):
        """Сброс всех метрик (начало новой сессии)"""
        self.requests_count = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_latency_ms = 0
        self.latencies = []
        self.errors_by_type = {}
        self.recent_requests_timestamps = []
        self.anomalies_detected = 0
        self.session_start = time.time()
        self.last_save_time = time.time()
        
        self.logger.info("Метрики сброшены, начата новая сессия")
    
    def get_health_status(self) -> Dict:
        metrics = self.get_metrics()
        issues = []
        
        # Процент ошибок
        if metrics["error_rate"] > 0.5:
            issues.append(f"Критически высокий процент ошибок: {metrics['error_rate']:.1%}")
            status = "critical"
        elif metrics["error_rate"] > self.MAX_ERROR_RATE:
            issues.append(f"Повышенный процент ошибок: {metrics['error_rate']:.1%}")
            status = "degraded"
        else:
            status = "healthy"
        
        #  Задержка
        if metrics["latency"]["average_ms"] > self.MAX_LATENCY_MS * 2:
            issues.append(f"Критически высокая задержка: {metrics['latency']['average_ms']:.0f}мс")
            status = "critical"
        elif metrics["latency"]["average_ms"] > self.MAX_LATENCY_MS:
            issues.append(f"Повышенная задержка: {metrics['latency']['average_ms']:.0f}мс")
            if status == "healthy":
                status = "degraded"
        
        # Частота запросов
        if metrics["current_requests_per_minute"] > self.MAX_REQUESTS_PER_MINUTE * 1.5:
            issues.append(f"Очень высокая частота запросов: {metrics['current_requests_per_minute']}/мин")
            status = "critical"
        elif metrics["current_requests_per_minute"] > self.MAX_REQUESTS_PER_MINUTE:
            issues.append(f"Высокая частота запросов: {metrics['current_requests_per_minute']}/мин")
            if status == "healthy":
                status = "degraded"
        
        return {
            "status": status,
            "issues": issues,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое сохранение при выходе"""
        self.save_metrics()
        self.print_summary()

