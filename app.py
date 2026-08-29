
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
        and rsi >= 30
        and rsi <= 90
        and momentum > -2.00
        and volume_ratio >= 0.25
    ):

        entry = price

        recent_low = min(lows[-8:])

        stop = recent_low

        risk = entry - stop

        if risk <= 0:
            return None

        target = entry + (risk * 1.7)

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

        if score < 10:
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
        and rsi >= 10
        and rsi <= 78
        and momentum < 2.00
        and volume_ratio >= 0.20
    ):

        entry = price

        recent_high = max(highs[-8:])

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

        if score < 10:
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
# =========================================================
# SIMULAÇÃO E HISTÓRICO DE OPERAÇÕES
# =========================================================

import threading
import time
from datetime import datetime


# ---------------------------------------------------------
# CONFIGURAÇÕES DA SIMULAÇÃO
# ---------------------------------------------------------

INITIAL_CAPITAL = 1000.0

SIMULATION_CAPITAL = INITIAL_CAPITAL

MAX_OPEN_TRADES = 10

MIN_SCORE_TO_TRADE = 15

TRADE_RISK_PERCENT = 2.0

MONITOR_INTERVAL = 10


# ---------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------

def get_current_price(symbol: str):

    try:

        r = requests.get(
            f"{BINANCE}/api/v3/ticker/price",
            params={
                "symbol": symbol.upper()
            },
            timeout=10
        )

        r.raise_for_status()

        data = r.json()

        return float(data["price"])

    except Exception:

        return None


def get_open_trade(symbol: str):

    symbol = symbol.upper()

    for trade in TRADES:

        if (
            trade["symbol"] == symbol
            and trade["status"] == "OPEN"
        ):

            return trade

    return None


def get_open_trades():

    return [

        trade

        for trade in TRADES

        if trade["status"] == "OPEN"

    ]


# ---------------------------------------------------------
# ABRIR OPERAÇÃO SIMULADA
# ---------------------------------------------------------

def open_simulated_trade(signal):

    global SIMULATION_CAPITAL


    symbol = signal["symbol"]


    # Evita duplicar operação

    existing_trade = get_open_trade(symbol)

    if existing_trade is not None:

        return None


    # Limite máximo de operações abertas

    if len(get_open_trades()) >= MAX_OPEN_TRADES:

        return None


    score = signal.get("score", 0)


    if score < MIN_SCORE_TO_TRADE:

        return None


    entry = float(signal["entry"])

    stop = float(signal["stop"])

    target = float(signal["target"])

    side = signal["signal"]


    # Valor utilizado na operação

    position_value = (
        SIMULATION_CAPITAL
        * TRADE_RISK_PERCENT
    )


    trade = {

        "id": len(TRADES) + 1,

        "symbol": symbol,

        "side": side,

        "entry": entry,

        "stop": stop,

        "target": target,

        "score": score,

        "confidence": signal.get(
            "confidence",
            None
        ),

        "risk_reward": signal.get(
            "risk_reward",
            None
        ),

        "interval": signal.get(
            "interval",
            INTERVAL
        ),

        "position_value": position_value,

        "status": "OPEN",

        "opened_at": datetime.utcnow().isoformat(),

        "closed_at": None,

        "exit_price": None,

        "result": None,

        "profit_percent": 0.0,

        "profit_value": 0.0

    }


    TRADES.append(trade)


    return trade


# ---------------------------------------------------------
# FECHAR OPERAÇÃO
# ---------------------------------------------------------

def close_trade(
    trade,
    exit_price,
    result
):

    global SIMULATION_CAPITAL


    entry = float(trade["entry"])

    exit_price = float(exit_price)


    # ---------------------------------------------
    # BUY
    # ---------------------------------------------

    if trade["side"] == "BUY":

        profit_percent = (
            (
                exit_price - entry
            )
            / entry
        ) * 100


    # ---------------------------------------------
    # SELL / SHORT
    # ---------------------------------------------

    else:

        profit_percent = (
            (
                entry - exit_price
            )
            / entry
        ) * 100


    profit_value = (
        trade["position_value"]
        * profit_percent
        / 100
    )


    trade["exit_price"] = round(
        exit_price,
        8
    )

    trade["status"] = "CLOSED"

    trade["result"] = result

    trade["profit_percent"] = round(
        profit_percent,
        4
    )

    trade["profit_value"] = round(
        profit_value,
        2
    )

    trade["closed_at"] = (
        datetime.utcnow()
        .isoformat()
    )


    SIMULATION_CAPITAL += profit_value


    return trade


# ---------------------------------------------------------
# MONITORAR OPERAÇÕES ABERTAS
# ---------------------------------------------------------

def monitor_trades():

    while True:

        try:

            open_trades = get_open_trades()


            for trade in open_trades:


                symbol = trade["symbol"]


                current_price = (
                    get_current_price(symbol)
                )


                if current_price is None:

                    continue


                side = trade["side"]

                stop = float(
                    trade["stop"]
                )

                target = float(
                    trade["target"]
                )


                # =====================================
                # BUY
                # =====================================

                if side == "BUY":


                    # STOP

                    if current_price <= stop:

                        close_trade(

                            trade=trade,

                            exit_price=current_price,

                            result="LOSS"

                        )


                    # TARGET

                    elif current_price >= target:

                        close_trade(

                            trade=trade,

                            exit_price=current_price,

                            result="WIN"

                        )


                # =====================================
                # SELL / SHORT
                # =====================================

                elif side == "SELL":


                    # STOP

                    if current_price >= stop:

                        close_trade(

                            trade=trade,

                            exit_price=current_price,

                            result="LOSS"

                        )


                    # TARGET

                    elif current_price <= target:

                        close_trade(

                            trade=trade,

                            exit_price=current_price,

                            result="WIN"

                        )


        except Exception as e:

            print(
                "Erro no monitor de trades:",
                e
            )


        time.sleep(
            MONITOR_INTERVAL
        )


# ---------------------------------------------------------
# INICIAR MONITOR EM BACKGROUND
# ---------------------------------------------------------

trade_monitor = threading.Thread(

    target=monitor_trades,

    daemon=True

)


trade_monitor.start()


# =========================================================
# ABRIR OPERAÇÃO MANUAL A PARTIR DO RADAR
# =========================================================

@app.post("/trade/{symbol}")

def create_trade(symbol: str):


    result = analyze_symbol(
        symbol.upper()
    )


    if result is None:

        raise HTTPException(

            status_code=400,

            detail=(
                "Não foi possível "
                "analisar esta moeda"
            )

        )


    score = result.get(
        "score",
        0
    )


    if score < MIN_SCORE_TO_TRADE:

        return {

            "opened": False,

            "message": (
                "Score insuficiente "
                "para abrir operação"
            ),

            "minimum_score": (
                MIN_SCORE_TO_TRADE
            ),

            "signal": result

        }


    trade = open_simulated_trade(
        result
    )


    if trade is None:

        return {

            "opened": False,

            "message": (
                "Operação não aberta. "
                "Pode já existir uma operação "
                "nesta moeda ou o limite de "
                "operações abertas foi atingido."
            )

        }


    return {

        "opened": True,

        "mode": "simulated",

        "trade": trade

    }


# =========================================================
# VARREDURA AUTOMÁTICA + ABERTURA DE OPERAÇÕES
# =========================================================

@app.post("/auto-scan")

def auto_scan():


    opened_trades = []

    analyzed = 0


    for symbol in SYMBOLS:


        try:

            analyzed += 1


            result = analyze_symbol(
                symbol
            )


            if result is None:

                continue


            score = result.get(
                "score",
                0
            )


            if score < MIN_SCORE_TO_TRADE:

                continue


            trade = open_simulated_trade(
                result
            )


            if trade is not None:

                opened_trades.append(
                    trade
                )


        except Exception as e:

            print(
                f"Erro ao analisar "
                f"{symbol}:",
                e
            )

            continue


    return {

        "analyzed": analyzed,

        "opened": len(
            opened_trades
        ),

        "trades": opened_trades,

        "open_trades": len(
            get_open_trades()
        ),

        "max_open_trades": (
            MAX_OPEN_TRADES
        )

    }


# =========================================================
# LISTAR OPERAÇÕES ABERTAS
# =========================================================

@app.get("/trades/open")

def trades_open():


    open_trades = (
        get_open_trades()
    )


    updated_trades = []


    for trade in open_trades:


        current_price = (
            get_current_price(
                trade["symbol"]
            )
        )


        trade_data = (
            trade.copy()
        )


        if current_price is not None:

            entry = float(
                trade["entry"]
            )


            # BUY

            if trade["side"] == "BUY":

                current_percent = (

                    (
                        current_price - entry
                    )

                    / entry

                ) * 100


            # SELL

            else:

                current_percent = (

                    (
                        entry - current_price
                    )

                    / entry

                ) * 100


            trade_data[
                "current_price"
            ] = round(
                current_price,
                8
            )


            trade_data[
                "current_profit_percent"
            ] = round(
                current_percent,
                4
            )


            trade_data[
                "current_profit_value"
            ] = round(

                trade[
                    "position_value"
                ]

                * current_percent

                / 100,

                2

            )


        updated_trades.append(
            trade_data
        )


    return {

        "total_open": len(
            updated_trades
        ),

        "trades": updated_trades

    }


# =========================================================
# HISTÓRICO COMPLETO
# =========================================================

@app.get("/trades")

def all_trades():

    return {

        "total": len(
            TRADES
        ),

        "trades": TRADES

    }


# =========================================================
# ESTATÍSTICAS
# =========================================================

@app.get("/statistics")

def statistics_route():

    global SIMULATION_CAPITAL


    total = len(
        TRADES
    )


    open_count = len(
        get_open_trades()
    )


    closed_trades = [

        trade

        for trade in TRADES

        if trade["status"] == "CLOSED"

    ]


    wins = [

        trade

        for trade in closed_trades

        if trade["result"] == "WIN"

    ]


    losses = [

        trade

        for trade in closed_trades

        if trade["result"] == "LOSS"

    ]


    wins_count = len(
        wins
    )

    losses_count = len(
        losses
    )


    closed_count = len(
        closed_trades
    )


    win_rate = 0


    if closed_count > 0:

        win_rate = (

            wins_count

            / closed_count

        ) * 100


    total_profit = sum(

        trade["profit_value"]

        for trade in closed_trades

    )


    total_profit_percent = (

        (
            SIMULATION_CAPITAL
            - INITIAL_CAPITAL
        )

        / INITIAL_CAPITAL

    ) * 100


    return {

        "mode": "simulated",

        "initial_capital": (
            round(
                INITIAL_CAPITAL,
                2
            )
        ),

        "current_capital": (
            round(
                SIMULATION_CAPITAL,
                2
            )
        ),

        "total_analyzed_operations": (
            total
        ),

        "open_trades": (
            open_count
        ),

        "closed_trades": (
            closed_count
        ),

        "wins": wins_count,

        "losses": losses_count,

        "win_rate": round(
            win_rate,
            2
        ),

        "total_profit": round(
            total_profit,
            2
        ),

        "total_return_percent": round(
            total_profit_percent,
            2
        ),

        "maximum_open_trades": (
            MAX_OPEN_TRADES
        ),

        "minimum_score": (
            MIN_SCORE_TO_TRADE
        )

    }


# =========================================================
# RESETAR SIMULAÇÃO
# =========================================================

@app.post("/reset")

def reset_simulation():

    global SIMULATION_CAPITAL


    TRADES.clear()


    SIMULATION_CAPITAL = (
        INITIAL_CAPITAL
    )


    return {

        "status": "reset",

        "capital": (
            SIMULATION_CAPITAL
        )

    }


# =========================================================
# STATUS DO ROBÔ
# =========================================================

@app.get("/status")

def bot_status():

    return {

        "status": "online",

        "mode": "simulated",

        "symbols": len(
            SYMBOLS
        ),

        "interval": INTERVAL,

        "open_trades": len(
            get_open_trades()
        ),

        "total_trades": len(
            TRADES
        ),

        "capital": round(
            SIMULATION_CAPITAL,
            2
        )

    }
