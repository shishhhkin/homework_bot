class MissingTokenError(Exception):
    """Отсутствует обязательный токен."""

    pass


class ResponseError(Exception):
    """Ошибка ответа от YandexAPI."""

    pass


class MessageSendingError(Exception):
    """Ошибка отправки сообщения в телеграм."""

    pass
