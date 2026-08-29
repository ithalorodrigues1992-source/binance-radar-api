
from fastapi import FastAPI, HTTPException
import requests
import statistics
from typing import List, Dict, Optional


app = FastAPI(title="Binance Radar API")

BINANCE = "https://api.binance.com"


# =========================================================
# CONFIGURAÇÃO
# =========================================================

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "LTCUSDT",
    "DOTUSDT",
    "TRXUSDT",
    "ATOMUSDT",
    "NEARUSDT",
    "APTUSDT",
    "ARBUSDT",
    "OPUSDT",
    "INJUSDT",
    "FILUSDT"
]

INTERVAL = "5m"
LIMIT = 100
MIN_RISK_REWARD = 1.70


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def get_klines(symbol: str, interval: str = INTERVAL):

    try:

        r = requests.get(
            f"{BINANCE}/api/v3/klines",
            params={
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": LIMIT
            },
            timeout=10
        )

        r.raise_for_status()

        return r.json()

    except Exception as e:
        return []


def calculate_ema(values: List[float], period: int):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(values[:period]) / period

    for price in values[period:]:

        ema = (price - ema) * multiplier + ema

    return ema


def calculate_rsi(closes: List[float], period: int = 14):

    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, period + 1):

        change = closes[i] - closes[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)


def calculate_score(
    trend_ok: bool,
    rsi: float,
    volume_ratio: float,
    momentum: float,
    risk_reward: float
):

    score = 0

    # Tendência
    if trend_ok:
        score += 30

    # RSI
    if 50 <= rsi <= 70:
        score += 20

    elif 45 <= rsi <= 75:
        score += 10

    # Volume
    if volume_ratio >= 1.5:
        score += 25

    elif volume_ratio >= 1.1:
        score += 15

    elif volume_ratio >= 1:
        score += 5

    # Momentum
    if momentum > 1:
        score += 15

    elif momentum > 0:
        score += 8

    # Risk / Reward
    if risk_reward >= 3:
        score += 10

    elif risk_reward >= 2:
        score += 7

    elif risk_reward >= 1.7:
        score += 5

    return min(score, 100)


def confidence(score: int):

    if score >= 80:
        return "MUITO ALTA"

    if score >= 65:
        return "ALTA"

    if score >= 50:
        return "MEDIA"

    return "BAIXA"


# =========================================================
# ANALISAR UMA MOEDA
# =========================================================

def analyze_symbol(symbol: str):

    candles = get_klines(symbol)

    if len(candles) < 50:
        return None

    closes = [float(candle[4]) for candle in candles]
    highs = [float(candle[2]) for candle in candles]
    lows = [float(candle[3]) for candle in candles]
    volumes = [float(candle[5]) for candle in candles]

    price = closes[-1]

    # EMAs
    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)

    if ema9 is None or ema21 is None:
        return None

    # RSI
    rsi = calculate_rsi(closes[-15:])

    if rsi is None:
        return None

    # Volume
    recent_volume = volumes[-1]

    average_volume = statistics.mean(volumes[-21:-1])

    volume_ratio = (
        recent_volume / average_volume
        if average_volume > 0
        else 0
    )

    # Momentum em %
    price_5_candles_ago = closes[-6]

    momentum = (
        (price - price_5_candles_ago)
        / price_5_candles_ago
    ) * 100

    # Tendência
    bullish_trend = (
        price > ema9
        and ema9 > ema21
    )

    bearish_trend = (
        price < ema9
        and ema9 < ema21
    )

    # =====================================================
    # SINAL DE COMPRA
    # =====================================================

    if (
        bullish_trend
        and rsi >= 50
        and rsi <= 72
        and momentum > 0
        and volume_ratio >= 1.00
    ):

        entry = price

        recent_low = min(lows[-10:])

        stop = recent_low

        risk = entry - stop

        if risk <= 0:
            return None

        target = entry + (risk * 1.8)

        reward = target - entry

        risk_reward = reward / risk

        if risk_reward < MIN_RISK_REWARD:
            return None

        score = calculate_score(
            trend_ok=True,
            rsi=rsi,
            volume_ratio=volume_ratio,
            momentum=momentum,
            risk_reward=risk_reward
        )

        if score < 50:
            return None

        return {
            "symbol": symbol,
            "signal": "BUY",
            "entry": round(entry, 8),
            "stop": round(stop, 8),
            "target": round(target, 8),
            "risk_reward": round(risk_reward, 2),
            "score": score,
            "confidence": confidence(score),
            "price": round(price, 8),
            "ema9": round(ema9, 8),
            "ema21": round(ema21, 8),
            "rsi": rsi,
            "volume_ratio": round(volume_ratio, 2),
            "momentum_percent": round(momentum, 2),
            "interval": INTERVAL
        }

    # =====================================================
    # SINAL DE VENDA / SHORT
    # =====================================================

    if (
        bearish_trend
        and rsi >= 25
        and rsi <= 50
        and momentum < 0
        and volume_ratio >= 1.00
    ):

        entry = price

        recent_high = max(highs[-10:])

        stop = recent_high

        risk = stop - entry

        if risk <= 0:
            return None

        target = entry - (risk * 1.8)

        reward = entry - target

        risk_reward = reward / risk

        if risk_reward < MIN_RISK_REWARD:
            return None

        score = calculate_score(
            trend_ok=True,
            rsi=100 - rsi,
            volume_ratio=volume_ratio,
            momentum=abs(momentum),
            risk_reward=risk_reward
        )

        if score < 42:
            return None

        return {
            "symbol": symbol,
            "signal": "SELL",
            "entry": round(entry, 8),
            "stop": round(stop, 8),
            "target": round(target, 8),
            "risk_reward": round(risk_reward, 2),
            "score": score,
            "confidence": confidence(score),
            "price": round(price, 8),
            "ema9": round(ema9, 8),
            "ema21": round(ema21, 8),
            "rsi": rsi,
            "volume_ratio": round(volume_ratio, 2),
            "momentum_percent": round(momentum, 2),
            "interval": INTERVAL
        }

    return None


# =========================================================
# ROTAS
# =========================================================

@app.get("/")
def home():

    return {
        "status": "online",
        "mode": "simulado",
        "service": "Binance Radar API",
        "symbols": len(SYMBOLS),
        "interval": INTERVAL
    }


@app.get("/price/{symbol}")
def price(symbol: str):

    try:

        r = requests.get(
            f"{BINANCE}/api/v3/ticker/price",
            params={
                "symbol": symbol.upper()
            },
            timeout=10
        )

        r.raise_for_status()

        return r.json()

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel consultar este simbolo"
        )


@app.get("/radar/{symbol}")
def radar(symbol: str):

    result = analyze_symbol(symbol.upper())

    if result is None:

        return {
            "symbol": symbol.upper(),
            "opportunity": False,
            "message": "Nenhuma oportunidade encontrada agora",
            "interval": INTERVAL
        }

    return {
        "opportunity": True,
        "data": result
    }


@app.get("/scan")
def scan():

    opportunities = []

    analyzed = 0

    for symbol in SYMBOLS:

        analyzed += 1

        try:

            result = analyze_symbol(symbol)

            if result is not None:

                opportunities.append(result)

        except Exception:

            continue

    # Ordenar pelas melhores oportunidades
    opportunities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return {
        "total_analyzed": analyzed,
        "total_opportunities": len(opportunities),
        "opportunities": opportunities,
        "mode": "simulado",
        "interval": INTERVAL,
        "minimum_risk_reward": MIN_RISK_REWARD
    }


@app.get("/symbols")
def symbols():

    return {
        "total": len(SYMBOLS),
        "symbols": SYMBOLS
    }
# ============================================================
# SIMULAÇÃO E HISTÓRICO DE OPERAÇÕES
# ============================================================

TRADES = []
