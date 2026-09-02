from fastapi import FastAPI, HTTPException
import requests, statistics, threading, time
from datetime import datetime, timezone
from typing import List

app = FastAPI(title="Crypto Radar API", description="Radar automático de criptomoedas com simulação", version="2.1")
BINANCE = "https://api.binance.com"

SYMBOLS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","SUIUSDT",
    "LTCUSDT","DOTUSDT","TRXUSDT","ATOMUSDT","NEARUSDT","APTUSDT","ARBUSDT","OPUSDT","INJUSDT","FILUSDT",
    "TONUSDT","SHIBUSDT","PEPEUSDT","FLOKIUSDT","BONKUSDT","WIFUSDT","TIAUSDT","SEIUSDT","RUNEUSDT",
    "AAVEUSDT","MKRUSDT","UNIUSDT","SNXUSDT","CRVUSDT","COMPUSDT","SUSHIUSDT","GRTUSDT","FETUSDT","RENDERUSDT",
    "TAOUSDT","JUPUSDT","PYTHUSDT","ORDIUSDT","ICPUSDT","XLMUSDT","ETCUSDT","ALGOUSDT","VETUSDT",
    "SANDUSDT","MANAUSDT","AXSUSDT","GALAUSDT","APEUSDT","CHZUSDT","ENJUSDT","KAVAUSDT","FLOWUSDT",
    "EGLDUSDT","THETAUSDT","ZECUSDT","DASHUSDT","NEOUSDT","IOTAUSDT"
]

INTERVAL = "5m"
LIMIT = 100

# NOVO: o radar mostra oportunidades a partir de 40
MIN_SCORE_TO_SHOW = 40

# O robô só abre operações a partir de 55
MIN_SCORE_TO_TRADE = 55

MIN_RISK_REWARD = 1.5

INITIAL_CAPITAL = 1000.0
SIMULATION_CAPITAL = INITIAL_CAPITAL
MAX_OPEN_TRADES = 5
TRADE_RISK_PERCENT = 2.0
MONITOR_INTERVAL = 15
TRADES = []


def binance_request(endpoint: str, params=None):
    try:
        r = requests.get(f"{BINANCE}{endpoint}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_current_price(symbol: str):
    data = binance_request("/api/v3/ticker/price", {"symbol": symbol.upper()})
    try:
        return float(data["price"]) if data else None
    except Exception:
        return None


def get_klines(symbol: str):
    data = binance_request("/api/v3/klines", {
        "symbol": symbol.upper(), "interval": INTERVAL, "limit": LIMIT
    })
    return data or []


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
    gains, losses = [], []
    for i in range(len(closes) - period, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_score(bullish_trend, bearish_trend, rsi, volume_ratio, momentum, risk_reward):
    score = 0
    if bullish_trend or bearish_trend:
        score += 30

    if 50 <= rsi <= 70:
        score += 20
    elif 40 <= rsi <= 80:
        score += 10

    if volume_ratio >= 2:
        score += 25
    elif volume_ratio >= 1.5:
        score += 20
    elif volume_ratio >= 1.2:
        score += 15
    elif volume_ratio >= 1:
        score += 5

    m = abs(momentum)
    if m >= 2:
        score += 15
    elif m >= 1:
        score += 10
    elif m > 0.3:
        score += 5

    if risk_reward >= 3:
        score += 10
    elif risk_reward >= 2:
        score += 7
    elif risk_reward >= 1.5:
        score += 5

    return min(score, 100)


def confidence(score: int):
    if score >= 85: return "MUITO ALTA"
    if score >= 70: return "ALTA"
    if score >= 55: return "MEDIA"
    return "BAIXA"


def analyze_symbol(symbol: str):
    candles = get_klines(symbol)
    if len(candles) < 50:
        return None

    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    volumes = [float(c[5]) for c in candles]

    price = closes[-1]
    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    rsi = calculate_rsi(closes, 14)

    if ema9 is None or ema21 is None or rsi is None:
        return None

    avg_volume = statistics.mean(volumes[-21:-1])
    volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 0

    previous_price = closes[-6]
    momentum = ((price - previous_price) / previous_price) * 100

    bullish = ema9 > ema21 and price > ema9
    bearish = ema9 < ema21 and price < ema9

    signal = None
    entry = price

    if bullish and 45 <= rsi <= 75 and momentum > 0:
        signal = "BUY"
        stop = min(lows[-8:])
        risk = entry - stop
        if risk <= 0:
            return None
        target = entry + risk * 2
        score_rsi = rsi

    elif bearish and 25 <= rsi <= 55 and momentum < 0:
        signal = "SELL"
        stop = max(highs[-8:])
        risk = stop - entry
        if risk <= 0:
            return None
        target = entry - risk * 2
        score_rsi = 100 - rsi

    else:
        return None

    risk_reward = 2.0
    if risk_reward < MIN_RISK_REWARD:
        return None

    score = calculate_score(
        bullish_trend=bullish if signal == "BUY" else False,
        bearish_trend=bearish if signal == "SELL" else False,
        rsi=score_rsi,
        volume_ratio=volume_ratio,
        momentum=momentum,
        risk_reward=risk_reward
    )

    # NOVO: aqui usamos 40, para o /scan encontrar mais oportunidades
    if score < MIN_SCORE_TO_SHOW:
        return None

    return {
        "symbol": symbol,
        "signal": signal,
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


def get_open_trades():
    return [t for t in TRADES if t["status"] == "OPEN"]


def get_open_trade(symbol):
    symbol = symbol.upper()
    return next((t for t in TRADES if t["symbol"] == symbol and t["status"] == "OPEN"), None)


def open_simulated_trade(signal):
    global SIMULATION_CAPITAL

    if get_open_trade(signal["symbol"]) or len(get_open_trades()) >= MAX_OPEN_TRADES:
        return None

    # Mantém 55 para abrir operação
    if signal["score"] < MIN_SCORE_TO_TRADE:
        return None

    position_value = SIMULATION_CAPITAL * (TRADE_RISK_PERCENT / 100)

    trade = {
        "id": len(TRADES) + 1,
        "symbol": signal["symbol"],
        "side": signal["signal"],
        "entry": signal["entry"],
        "stop": signal["stop"],
        "target": signal["target"],
        "score": signal["score"],
        "confidence": signal["confidence"],
        "risk_reward": signal["risk_reward"],
        "position_value": round(position_value, 2),
        "status": "OPEN",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "closed_at": None,
        "exit_price": None,
        "result": None,
        "profit_percent": 0,
        "profit_value": 0
    }
    TRADES.append(trade)
    return trade


def close_trade(trade, exit_price, result):
    global SIMULATION_CAPITAL
    entry = float(trade["entry"])
    pct = ((exit_price - entry) / entry * 100) if trade["side"] == "BUY" else ((entry - exit_price) / entry * 100)
    value = trade["position_value"] * pct / 100

    trade.update({
        "exit_price": round(exit_price, 8),
        "profit_percent": round(pct, 4),
        "profit_value": round(value, 2),
        "status": "CLOSED",
        "result": result,
        "closed_at": datetime.now(timezone.utc).isoformat()
    })
    SIMULATION_CAPITAL += value


def monitor_trades():
    while True:
        try:
            for trade in get_open_trades():
                price = get_current_price(trade["symbol"])
                if price is None:
                    continue
                stop, target = float(trade["stop"]), float(trade["target"])

                if trade["side"] == "BUY":
                    if price <= stop: close_trade(trade, price, "LOSS")
                    elif price >= target: close_trade(trade, price, "WIN")
                else:
                    if price >= stop: close_trade(trade, price, "LOSS")
                    elif price <= target: close_trade(trade, price, "WIN")
        except Exception as e:
            print("Erro monitor:", e)

        time.sleep(MONITOR_INTERVAL)


threading.Thread(target=monitor_trades, daemon=True).start()


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Crypto Radar",
        "mode": "simulation",
        "symbols": len(SYMBOLS),
        "interval": INTERVAL,
        "capital": SIMULATION_CAPITAL,
        "minimum_score_to_show": MIN_SCORE_TO_SHOW,
        "minimum_score_to_trade": MIN_SCORE_TO_TRADE
    }


@app.get("/price/{symbol}")
def price(symbol: str):
    current = get_current_price(symbol)
    if current is None:
        raise HTTPException(status_code=400, detail="Não foi possível consultar a moeda")
    return {"symbol": symbol.upper(), "price": current}


@app.get("/radar/{symbol}")
def radar(symbol: str):
    result = analyze_symbol(symbol.upper())
    if result is None:
        return {
            "symbol": symbol.upper(),
            "opportunity": False,
            "message": "Nenhuma oportunidade encontrada",
            "interval": INTERVAL,
            "minimum_score_to_show": MIN_SCORE_TO_SHOW
        }
    return {"opportunity": True, "data": result}


@app.get("/scan")
def scan():
    opportunities = []
    for symbol in SYMBOLS:
        try:
            result = analyze_symbol(symbol)
            if result:
                opportunities.append(result)
        except Exception:
            continue

    opportunities.sort(key=lambda x: x["score"], reverse=True)

    return {
        "total_analyzed": len(SYMBOLS),
        "total_opportunities": len(opportunities),
        "opportunities": opportunities,
        "interval": INTERVAL,
        "minimum_score_to_show": MIN_SCORE_TO_SHOW
    }


@app.post("/trade/{symbol}")
def create_trade(symbol: str):
    signal = analyze_symbol(symbol.upper())

    if signal is None:
        raise HTTPException(status_code=400, detail="Nenhum sinal disponível")

    if signal["score"] < MIN_SCORE_TO_TRADE:
        return {
            "opened": False,
            "message": "Sinal encontrado, mas score insuficiente para abrir operação",
            "minimum_score_to_trade": MIN_SCORE_TO_TRADE,
            "signal": signal
        }

    trade = open_simulated_trade(signal)
    if trade is None:
        return {"opened": False, "message": "Operação não aberta"}

    return {"opened": True, "trade": trade}


@app.post("/auto-scan")
def auto_scan():
    opened = []
    for symbol in SYMBOLS:
        try:
            signal = analyze_symbol(symbol)
            if signal and signal["score"] >= MIN_SCORE_TO_TRADE:
                trade = open_simulated_trade(signal)
                if trade:
                    opened.append(trade)
        except Exception:
            continue

    return {
        "opened": len(opened),
        "trades": opened,
        "open_trades": len(get_open_trades()),
        "minimum_score_to_trade": MIN_SCORE_TO_TRADE
    }


@app.get("/trades/open")
def open_trades_route():
    data = []
    for trade in get_open_trades():
        item = trade.copy()
        current = get_current_price(trade["symbol"])
        if current is not None:
            entry = float(trade["entry"])
            pct = ((current-entry)/entry*100) if trade["side"] == "BUY" else ((entry-current)/entry*100)
            item["current_price"] = round(current, 8)
            item["current_profit_percent"] = round(pct, 4)
            item["current_profit_value"] = round(trade["position_value"] * pct / 100, 2)
        data.append(item)
    return {"total": len(data), "trades": data}


@app.get("/trades")
def all_trades():
    return {"total": len(TRADES), "trades": TRADES}


@app.get("/statistics")
def statistics_route():
    closed = [t for t in TRADES if t["status"] == "CLOSED"]
    wins = [t for t in closed if t["result"] == "WIN"]
    losses = [t for t in closed if t["result"] == "LOSS"]
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    total_profit = sum(t["profit_value"] for t in closed)

    return {
        "initial_capital": INITIAL_CAPITAL,
        "current_capital": round(SIMULATION_CAPITAL, 2),
        "open_trades": len(get_open_trades()),
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_profit": round(total_profit, 2),
        "total_return_percent": round((SIMULATION_CAPITAL - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2),
        "minimum_score_to_show": MIN_SCORE_TO_SHOW,
        "minimum_score_to_trade": MIN_SCORE_TO_TRADE
    }


@app.post("/reset")
def reset():
    global SIMULATION_CAPITAL
    TRADES.clear()
    SIMULATION_CAPITAL = INITIAL_CAPITAL
    return {"status": "reset", "capital": SIMULATION_CAPITAL}


@app.get("/status")
def status():
    return {
        "status": "online",
        "capital": SIMULATION_CAPITAL,
        "symbols": len(SYMBOLS),
        "open_trades": len(get_open_trades()),
        "total_trades": len(TRADES),
        "interval": INTERVAL,
        "minimum_score_to_show": MIN_SCORE_TO_SHOW,
        "minimum_score_to_trade": MIN_SCORE_TO_TRADE
    }

