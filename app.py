from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import statistics

app = FastAPI(title="Binance Radar API")

BINANCE = "https://api.binance.com"


# =========================================================
# MODELOS
# =========================================================

class Signal(BaseModel):
    symbol: str
    entry: float
    stop: float
    target: float


# =========================================================
# STATUS
# =========================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "mode": "simulado",
        "service": "Binance Radar API"
    }


# =========================================================
# PREÇO ATUAL
# =========================================================

@app.get("/price/{symbol}")
def price(symbol: str):

    try:

        r = requests.get(
            f"{BINANCE}/api/v3/ticker/price",
            params={"symbol": symbol.upper()},
            timeout=10
        )

        r.raise_for_status()

        data = r.json()

        return {
            "symbol": data["symbol"],
            "price": float(data["price"])
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao consultar preço: {str(e)}"
        )


# =========================================================
# CÁLCULO MANUAL DE RISCO / RETORNO
# =========================================================

@app.post("/signal")
def signal(s: Signal):

    risk = abs(s.entry - s.stop)
    reward = abs(s.target - s.entry)

    rr = round(reward / risk, 2) if risk else None

    return {
        **s.model_dump(),
        "risk_reward": rr,
        "mode": "simulado"
    }


# =========================================================
# FUNÇÃO DE MÉDIA MÓVEL
# =========================================================

def sma(values, period):

    if len(values) < period:
        return None

    return sum(values[-period:]) / period


# =========================================================
# FUNÇÃO RSI
# =========================================================

def calculate_rsi(closes, period=14):

    if len(closes) < period + 1:
        return 50

    gains = []
    losses = []

    for i in range(1, len(closes)):

        change = closes[i] - closes[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)


# =========================================================
# ANÁLISE INDIVIDUAL
# =========================================================

def analyze_symbol(symbol: str):

    try:

        r = requests.get(
            f"{BINANCE}/api/v3/klines",
            params={
                "symbol": symbol.upper(),
                "interval": "5m",
                "limit": 100
            },
            timeout=10
        )

        r.raise_for_status()

        candles = r.json()

        closes = [
            float(candle[4])
            for candle in candles
        ]

        highs = [
            float(candle[2])
            for candle in candles
        ]

        lows = [
            float(candle[3])
            for candle in candles
        ]

        price = closes[-1]

        sma9 = sma(closes, 9)
        sma21 = sma(closes, 21)

        rsi = calculate_rsi(closes)

        # =================================================
        # MOMENTUM
        # =================================================

        momentum = 0

        if len(closes) >= 6:
            momentum = (
                (closes[-1] - closes[-6])
                / closes[-6]
            ) * 100

        momentum = round(momentum, 3)

        # =================================================
        # VOLATILIDADE
        # =================================================

        recent_prices = closes[-20:]

        volatility = statistics.pstdev(
            recent_prices
        ) if len(recent_prices) > 1 else 0

        volatility_percent = (
            volatility / price
        ) * 100

        volatility_percent = round(
            volatility_percent,
            3
        )

        # =================================================
        # SINAL
        # =================================================

        signal = "AGUARDAR"
        score = 0

        # Tendência de alta
        if sma9 and sma21 and sma9 > sma21:
            score += 1

        # Tendência de baixa
        if sma9 and sma21 and sma9 < sma21:
            score -= 1

        # RSI favorável para compra
        if 50 <= rsi <= 70:
            score += 1

        # RSI favorável para venda
        if 30 <= rsi <= 50:
            score -= 1

        # Momentum
        if momentum > 0:
            score += 1

        if momentum < 0:
            score -= 1

        # =================================================
        # COMPRA
        # =================================================

        if score >= 3:

            signal = "COMPRA"

            stop = price * 0.98

            target = price * 1.04

        # =================================================
        # VENDA / ALERTA DE QUEDA
        # =================================================

        elif score <= -3:

            signal = "VENDA"

            stop = price * 1.02

            target = price * 0.96

        else:

            signal = "ANALISE"

            stop = price

            target = price

        # =================================================
        # RISCO / RETORNO
        # =================================================

        risk = abs(price - stop)

        reward = abs(target - price)

        risk_reward = (
            round(reward / risk, 2)
            if risk > 0
            else None
        )

        return {
            "symbol": symbol.upper(),
            "price": round(price, 8),
            "signal": signal,
            "score": score,
            "sma9": round(sma9, 8),
            "sma21": round(sma21, 8),
            "rsi": rsi,
            "momentum_percent": momentum,
            "volatility_percent": volatility_percent,
            "entry": round(price, 8),
            "stop": round(stop, 8),
            "target": round(target, 8),
            "risk_reward": risk_reward,
            "interval": "5m",
            "mode": "simulado"
        }

    except Exception as e:

        return {
            "symbol": symbol.upper(),
            "error": str(e)
        }


# =========================================================
# RADAR INDIVIDUAL
# =========================================================

@app.get("/radar/{symbol}")
def radar_symbol(symbol: str):

    result = analyze_symbol(symbol)

    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    return result


# =========================================================
# LISTA DE MOEDAS DO RADAR
# =========================================================

RADAR_SYMBOLS = [

    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",

    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT",

    "LTCUSDT",
    "TRXUSDT",
    "SUIUSDT",
    "TONUSDT",
    "ATOMUSDT",

    "NEARUSDT",
    "APTUSDT",
    "ARBUSDT",
    "OPUSDT",
    "INJUSDT"
]


# =========================================================
# RADAR AUTOMÁTICO
# =========================================================

@app.get("/radar")
def radar(limit: int = 20):

    limit = max(1, min(limit, len(RADAR_SYMBOLS)))

    symbols = RADAR_SYMBOLS[:limit]

    opportunities = []

    analyzed = []

    for symbol in symbols:

        result = analyze_symbol(symbol)

        if "error" not in result:

            analyzed.append(result)

            # Só adiciona oportunidades
            # com sinal forte
            if (
                result["signal"]
                in ["COMPRA", "VENDA"]
                and result["risk_reward"] is not None
                and result["risk_reward"] >= 2
            ):

                opportunities.append(result)

    # Ordenar pelo score
    opportunities.sort(
        key=lambda x: abs(x["score"]),
        reverse=True
    )

    return {

        "total_analyzed": len(analyzed),

        "total_opportunities":
        len(opportunities),

        "opportunities":
        opportunities,

        "mode": "simulado",

        "interval": "5m"
    }
