def build_signal_text(signal: dict, symbol: str, timeframe: str) -> str:
    price = signal.get("price")
    sig = signal["signal"]

    if sig == "BUYX":
        return (
            f"{symbol} ({timeframe}) | WAVEX\n"
            f"🟢 ВХОЖУ В LONG\n\n"
            f"Открытие: {price} \n\n"
            f"#{symbol} #WAVEX"
        )

    if sig.startswith("AVER"):
        return (
            f"{symbol} ({timeframe}) | WAVEX\n"
            f"🟡 ДОКУПАЮ {sig}\n\n"
            f"Цена: {price} \n\n"
            f"#{symbol} #WAVEX"
        )

    if sig == "CLOSEX":
        return (
            f"{symbol} ({timeframe}) | WAVEX\n"
            f"🔴 ВЫХОЖУ ИЗ ПОЗИЦИИ\n\n"
            f"Цена: {price}\n\n"
            f"#{symbol} #WAVEX"
        )

    return ""