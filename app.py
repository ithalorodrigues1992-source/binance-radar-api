from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI(title="Binance Radar API", version="1.0.0")

BINANCE = "https://data-api.binance.vision"

class Signal(BaseModel):
    symbol: str
    side: str
    entry: float
    stop: float
    target: float

@app.get("/")
def root():
    return {"status": "online", "mode": "simulado"}

@app.get("/price/{symbol}")
def price(symbol: str):
    r = requests.get(f"{BINANCE}/api/v3/ticker/price",
                     params={"symbol": symbol.upper()}, timeout=10)
    r.raise_for_status()
    return r.json()

@app.post("/signal")
def signal(s: Signal):
    risk = abs(s.entry - s.stop)
    reward = abs(s.target - s.entry)
    rr = round(reward / risk, 2) if risk else None
    return {**s.model_dump(), "risk_reward": rr, "mode": "simulado
    @app.get("/radar/{symbol}")
def radar(symbol: str):

    r = requests.get(
        f"{BINANCE}/api/v3/klines",
        params={
            "symbol": symbol.upper(),
            "interval": "5m",
            "limit": 50
        },
        timeout=10
    )

    r.raise_for_status()

    candles = r.json()

    closes = [float(candle[4]) for candle in candles]

    price = closes[-1]

    sma9 = sum(closes[-9:]) / 9
    sma21 = sum(closes[-21:]) / 21

    gains = []
    losses = []

    for i in range(1, 15):
        change = closes[-i] - closes[-i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    if sma9 > sma21 and rsi < 70:
        signal = "COMPRA"
        stop = price * 0.98
        target = price * 1.04

    elif sma9 < sma21 and rsi > 30:
        signal = "VENDA"
        stop = price * 1.02
        target = price * 0.96

    else:
        signal = "AGUARDAR"
        stop = price
        target = price

    return {
        "symbol": symbol.upper(),
        "price": round(price, 4),
        "signal": signal,
        "sma9": round(sma9, 4),
        "sma21": round(sma21, 4),
        "rsi": round(rsi, 2),
        "entry": round(price, 4),
        "stop": round(stop, 4),
        "target": round(target, 4),
        "risk_reward": 2,
        "interval": "5m",
        "mode": "simulado"
    }
@app.get("/radar")
def radar_geral():

    symbols = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "DOTUSDT"
    ]

    oportunidades = []

    for symbol in symbols:
        try:

            r = requests.get(
                f"{BINANCE}/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": "5m",
                    "limit": 30
                },
                timeout=10
            )

            r.raise_for_status()

            candles = r.json()

            closes = [
                float(candle[4])
                for candle in candles
            ]

            price = closes[-1]

            sma9 = sum(closes[-9:]) / 9
            sma21 = sum(closes[-21:]) / 21

            gains = []
            losses = []

            for i in range(1, 15):

                change = closes[-i] - closes[-i - 1]

                if change >= 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            if sma9 > sma21 and rsi < 70:

                signal = "COMPRA"
                stop = price * 0.98
                target = price * 1.04

            elif sma9 < sma21 and rsi > 30:

                signal = "VENDA"
                stop = price * 1.02
                target = price * 0.96

            else:

                signal = "AGUARDAR"
                stop = price
                target = price

            if signal != "AGUARDAR":

                oportunidades.append({
                    "symbol": symbol,
                    "price": round(price, 4),
                    "signal": signal,
                    "sma9": round(sma9, 4),
                    "sma21": round(sma21, 4),
                    "rsi": round(rsi, 2),
                    "entry": round(price, 4),
                    "stop": round(stop, 4),
                    "target": round(target, 4),
                    "risk_reward": 2,
                    "interval": "5m"
                })

        except Exception as e:

            continue

    return {
        "total_opportunities": len(oportunidades),
        "opportunities": oportunidades,
        "mode": "simulado"
        }
