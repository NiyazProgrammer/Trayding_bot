from enum import Enum
from typing import Optional, Dict, Any
import logging
import time
import traceback
from utils.logging_setup import setup_logger

class ErrorType(Enum):
    """Enumeration of error types for categorization"""
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    SYSTEM_ERROR = "system_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTHENTICATION_ERROR = "authentication_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"

class UnifiedErrorHandler:
    """Centralized error handling system for the trading bot"""
    
    def __init__(self, logger_name: str = "UnifiedErrorHandler"):
        self.logger = setup_logger()
        self.error_counts = {}
        
    def handle_error(
        self, 
        error: Exception, 
        error_type: ErrorType, 
        context: Optional[Dict[str, Any]] = None,
        should_raise: bool = False,
        should_log: bool = True
    ) -> Dict[str, Any]:
        """
        Handle an error with centralized logging and response formatting
        """
        error_type_str = error_type.value
        self.error_counts[error_type_str] = self.error_counts.get(error_type_str, 0) + 1
        
        error_response = {
            "success": False,
            "error_type": error_type_str,
            "error_message": str(error),
            "timestamp": time.time(),
            "context": context or {}
        }
        
        if should_log:
            log_message = f"[{error_type_str.upper()}] {str(error)}"
            if context:
                log_message += f" | Context: {context}"
            
            # Log based on error type
            if error_type in [ErrorType.NETWORK_ERROR, ErrorType.SYSTEM_ERROR, ErrorType.UNKNOWN_ERROR]:
                self.logger.error(log_message)
                if hasattr(error, '__traceback__'):
                    self.logger.debug(f"Traceback: {traceback.format_tb(error.__traceback__)}")
            elif error_type in [ErrorType.API_ERROR, ErrorType.RATE_LIMIT_ERROR]:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)
        
        # Re-raise if requested
        if should_raise:
            raise error
            
        return error_response
    
    def handle_api_error(
        self, 
        status_code: int, 
        response_data: Dict, 
        operation: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle API-specific errors
        """
        context = context or {}
        context.update({"operation": operation, "status_code": status_code})
        
        # Handle specific status codes
        if status_code == 429:
            error_type = ErrorType.RATE_LIMIT_ERROR
            self.logger.warning(f"Rate limit exceeded for operation: {operation}")
            context["rate_limit_info"] = {
                "delay_seconds": 5,  # Default delay
                "retry_after": time.time() + 5
            }
        elif status_code >= 500:
            error_type = ErrorType.API_ERROR
        elif status_code >= 400:
            error_type = ErrorType.VALIDATION_ERROR
        else:
            error_type = ErrorType.API_ERROR
            
        api_code = response_data.get("code", "unknown")
        api_message = response_data.get("msg", response_data.get("message", "Unknown API error"))
        
        return self.handle_error(
            Exception(f"API Error {api_code}: {api_message}"),
            error_type,
            context
        )
    
    def retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        base_delay: float = 1.0,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Execute a function with exponential backoff retry logic
        """
        last_exception = Exception("Unknown error")
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                last_exception = e
                context = context or {}
                context["retry_attempt"] = attempt + 1
                context["max_retries"] = max_retries
                
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.handle_error(
                        e,
                        ErrorType.NETWORK_ERROR,
                        {**context, "retry_delay": delay},
                        should_log=True
                    )
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    self.handle_error(
                        e,
                        ErrorType.NETWORK_ERROR,
                        context,
                        should_log=True,
                        should_raise=False
                    )
        
        raise last_exception
    
    def get_error_statistics(self) -> Dict[str, int]:
        """Get statistics on error occurrences"""
        return self.error_counts.copy()
    
    def reset_error_counts(self):
        """Reset error counters"""
        self.error_counts.clear()

# Global instance for use across the application
global_error_handler = UnifiedErrorHandler()