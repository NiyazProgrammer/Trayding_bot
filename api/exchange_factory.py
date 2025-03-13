from .bitget_connector import BitgetConnector

class ExchangeFactory:
    @staticmethod
    def create_connector(exchange_name):
        if exchange_name == "bitget":
            return BitgetConnector()
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")