from .bitget_connector import BitgetConnector

class ExchangeFactory:
    @staticmethod
    def create_connector(exchange_name, demo_trading=False):
        if exchange_name == "bitget":
            return BitgetConnector(demo_trading=demo_trading)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")