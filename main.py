from api.exchange_factory import ExchangeFactory

def main():
    exchange = ExchangeFactory.create_connector("bitget")

    # Пример получения баланса и цены
    try:
        # Получение баланса
        balance = exchange.fetch_balance()
        print("Баланс:", balance['data'][0]['usdtBalance'])
    except Exception as e:
        print("Ошибка при получении баланса:", e)

    try:
        # Получение цены
        ticker = exchange.fetch_ticker("BTCUSDT")
        print("Текущая цена:", ticker['data'][0]['lastPr'])
    except Exception as e:
        print("Ошибка при получении цены:", e)
        

if __name__ == "__main__":
    main()