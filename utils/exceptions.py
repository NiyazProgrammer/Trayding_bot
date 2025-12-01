class MissingAPIKeyError(Exception):
    """
    Исключение выбрасывается когда отсутствует обязательный API ключ
    """
    def __init__(self, key_name: str, message: str = None):
        self.key_name = key_name
        if message is None:
            message = (
                f"Отсутствует обязательный API ключ: {key_name}\n"
                f"Убедитесь, что в .env файле установлена переменная {key_name}"
            )
        super().__init__(message)


class InvalidAPIKeyError(Exception):
    """
    Исключение выбрасывается когда API ключ имеет неправильный формат
    """
    def __init__(self, key_name: str, message: str = None):
        self.key_name = key_name
        if message is None:
            message = f"Неправильный формат API ключа: {key_name}"
        super().__init__(message)


class APIKeySecurityError(Exception):
    """
    Исключение выбрасывается при проблемах безопасности с API ключами
    """
    pass

