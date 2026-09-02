
from fastapi import FastAPI, HTTPException
import requests
import statistics
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Crypto Radar API",
    description="Radar automático de criptomoedas com simulação",
    version="2.0"
)


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
    "FILUSDT",

    "TONUSDT",
    "SHIBUSDT",
    "PEPEUSDT",
    "FLOKIUSDT",
    "BONKUSDT",

    "WIFUSDT",
    "TIAUSDT",
    "SEIUSDT",
    "RUNEUSDT",

    "AAVEUSDT",
    "MKRUSDT",
    "UNIUSDT",
    "SNXUSDT",
    "CRVUSDT",

    "COMPUSDT",
    "SUSHIUSDT",
    "GRTUSDT",
    "FETUSDT",
    "RENDERUSDT",

    "TAOUSDT",
    "JUPUSDT",
    "PYTHUSDT",
    "ORDIUSDT",

    "ICPUSDT",
    "XLMUSDT",
    "ETCUSDT",
    "ALGOUSDT",
    "VETUSDT",

    "SANDUSDT",
    "MANAUSDT",
    "AXSUSDT",
    "GALAUSDT",
    "APEUSDT",

    "CHZUSDT",
    "ENJUSDT",
    "KAVAUSDT",
    "FLOWUSDT",
    "EGLDUSDT",

    "THETAUSDT",
    "ZECUSDT",
    "DASHUSDT",
    "NEOUSDT",
    "IOTAUSDT"
]


INTERVAL = "5m"

LIMIT = 100

MIN_SCORE_TO_TRADE = 55

MIN_RISK_REWARD = 1.5


# =========================================================
# SIMULAÇÃO
# =========================================================

INITIAL_CAPITAL = 1000.0

SIMULATION_CAPITAL = INITIAL_CAPITAL

MAX_OPEN_TRADES = 5

TRADE_RISK_PERCENT = 2.0

MONITOR_INTERVAL = 15


TRADES = []


# =========================================================
# FUNÇÃO API BINANCE
# =========================================================

def binance_request(endpoint: str, params=None):

    try:

        response = requests.get(

            f"{BINANCE}{endpoint}",

            params=params,

            timeout=10

        )

        response.raise_for_status()

        return response.json()

    except Exception:

        return None


# =========================================================
# PREÇO ATUAL
# =========================================================

def get_current_price(symbol: str):

    data = binance_request(

        "/api/v3/ticker/price",

        {
            "symbol": symbol.upper()
        }

    )

    if not data:

        return None

    try:

        return float(data["price"])

    except Exception:

        return None


# =========================================================
# CANDLES
# =========================================================

def get_klines(symbol: str):

    data = binance_request(

        "/api/v3/klines",

        {
            "symbol": symbol.upper(),
            "interval": INTERVAL,
            "limit": LIMIT
        }

    )

    if not data:

        return []

    return data


# =========================================================
# EMA
# =========================================================

def calculate_ema(
    values: List[float],
    period: int
):

    if len(values) < period:

        return None


    multiplier = 2 / (period + 1)


    ema = sum(
        values[:period]
    ) / period


    for price in values[period:]:

        ema = (

            (price - ema)
            * multiplier

        ) + ema


    return ema


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    closes: List[float],
    period: int = 14
):

    if len(closes) < period + 1:

        return None


    gains = []

    losses = []


    for i in range(

        len(closes) - period,

        len(closes)

    ):


        change = (

            closes[i]
            - closes[i - 1]

        )


        if change >= 0:

            gains.append(
                change
            )

            losses.append(
                0
            )


        else:

            gains.append(
                0
            )

            losses.append(
                abs(change)
            )


    average_gain = (

        sum(gains)
        / period

    )


    average_loss = (

        sum(losses)
        / period

    )


    if average_loss == 0:

        return 100


    rs = (

        average_gain
        / average_loss

    )


    rsi = (

        100
        -
        (
            100
            /
            (1 + rs)
        )

    )


    return round(
        rsi,
        2
    )


# =========================================================
# SCORE
# =========================================================

def calculate_score(

    bullish_trend: bool,

    bearish_trend: bool,

    rsi: float,

    volume_ratio: float,

    momentum: float,

    risk_reward: float

):

    score = 0


    # -----------------------------------------------------
    # TENDÊNCIA
    # -----------------------------------------------------

    if bullish_trend:

        score += 30


    if bearish_trend:

        score += 30


    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if 50 <= rsi <= 70:

        score += 20


    elif 40 <= rsi <= 80:

        score += 10


    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    if volume_ratio >= 2:

        score += 25


    elif volume_ratio >= 1.5:

        score += 20


    elif volume_ratio >= 1.2:

        score += 15


    elif volume_ratio >= 1:

        score += 5


    # -----------------------------------------------------
    # MOMENTUM
    # -----------------------------------------------------

    absolute_momentum = abs(
        momentum
    )


    if absolute_momentum >= 2:

        score += 15


    elif absolute_momentum >= 1:

        score += 10


    elif absolute_momentum > 0.3:

        score += 5


    # -----------------------------------------------------
    # RISCO / RETORNO
    # -----------------------------------------------------

    if risk_reward >= 3:

        score += 10


    elif risk_reward >= 2:

        score += 7


    elif risk_reward >= 1.5:

        score += 5


    return min(
        score,
        100
    )


# =========================================================
# CONFIANÇA
# =========================================================

def confidence(score: int):

    if score >= 85:

        return "MUITO ALTA"


    if score >= 70:

        return "ALTA"


    if score >= 55:

        return "MEDIA"


    return "BAIXA"


# =========================================================
# ANALISAR MOEDA
# =========================================================

def analyze_symbol(symbol: str):


    candles = get_klines(
        symbol
    )


    if len(candles) < 50:

        return None


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


    volumes = [

        float(candle[5])

        for candle in candles

    ]


    price = closes[-1]


    # =====================================================
    # MÉDIAS
    # =====================================================

    ema9 = calculate_ema(

        closes,

        9

    )


    ema21 = calculate_ema(

        closes,

        21

    )


    if ema9 is None:

        return None


    if ema21 is None:

        return None


    # =====================================================
    # RSI
    # =====================================================

    rsi = calculate_rsi(

        closes,

        14

    )


    if rsi is None:

        return None


    # =====================================================
    # VOLUME
    # =====================================================

    recent_volume = (

        volumes[-1]

    )


    average_volume = (

        statistics.mean(
            volumes[-21:-1]
        )

    )


    if average_volume > 0:

        volume_ratio = (

            recent_volume
            /
            average_volume

        )

    else:

        volume_ratio = 0


    # =====================================================
    # MOMENTUM
    # =====================================================

    previous_price = (

        closes[-6]

    )


    momentum = (

        (
            price
            -
            previous_price
        )

        /
        previous_price

    ) * 100


    # =====================================================
    # TENDÊNCIA
    # =====================================================

    bullish_trend = (

        ema9 > ema21

        and

        price > ema9

    )


    bearish_trend = (

        ema9 < ema21

        and

        price < ema9

    )


    # =====================================================
    # BUY
    # =====================================================

    if (

        bullish_trend

        and

        rsi >= 45

        and

        rsi <= 75

        and

        momentum > 0

    ):


        entry = price


        stop = min(

            lows[-8:]

        )


        risk = (

            entry
            -
            stop

        )


        if risk <= 0:

            return None


        target = (

            entry
            +
            (
                risk
                *
                2
            )

        )


        reward = (

            target
            -
            entry

        )


        risk_reward = (

            reward
            /
            risk

        )


        score = calculate_score(

            bullish_trend=True,

            bearish_trend=False,

            rsi=rsi,

            volume_ratio=volume_ratio,

            momentum=momentum,

            risk_reward=risk_reward

        )


        if score < MIN_SCORE_TO_TRADE:

            return None


        return {

            "symbol": symbol,

            "signal": "BUY",

            "entry": round(
                entry,
                8
            ),

            "stop": round(
                stop,
                8
            ),

            "target": round(
                target,
                8
            ),

            "risk_reward": round(
                risk_reward,
                2
            ),

            "score": score,

            "confidence": confidence(
                score
            ),

            "price": round(
                price,
                8
            ),

            "ema9": round(
                ema9,
                8
            ),

            "ema21": round(
                ema21,
                8
            ),

            "rsi": rsi,

            "volume_ratio": round(
                volume_ratio,
                2
            ),

            "momentum_percent": round(
                momentum,
                2
            ),

            "interval": INTERVAL

        }


    # =====================================================
    # SELL
    # =====================================================

    if (

        bearish_trend

        and

        rsi >= 25

        and

        rsi <= 55

        and

        momentum < 0

    ):


        entry = price


        stop = max(

            highs[-8:]

        )


        risk = (

            stop
            -
            entry

        )


        if risk <= 0:

            return None


        target = (

            entry
            -
            (
                risk
                *
                2
            )

        )


        reward = (

            entry
            -
            target

        )


        risk_reward = (

            reward
            /
            risk

        )


        score = calculate_score(

            bullish_trend=False,

            bearish_trend=True,

            rsi=100 - rsi,

            volume_ratio=volume_ratio,

            momentum=momentum,

            risk_reward=risk_reward

        )


        if score < MIN_SCORE_TO_TRADE:

            return None


        return {

            "symbol": symbol,

            "signal": "SELL",

            "entry": round(
                entry,
                8
            ),

            "stop": round(
                stop,
                8
            ),

            "target": round(
                target,
                8
            ),

            "risk_reward": round(
                risk_reward,
                2
            ),

            "score": score,

            "confidence": confidence(
                score
            ),

            "price": round(
                price,
                8
            ),

            "ema9": round(
                ema9,
                8
            ),

            "ema21": round(
                ema21,
                8
            ),

            "rsi": rsi,

            "volume_ratio": round(
                volume_ratio,
                2
            ),

            "momentum_percent": round(
                momentum,
                2
            ),

            "interval": INTERVAL

        }


    return None


# =========================================================
# OPERAÇÕES
# =========================================================

def get_open_trades():

    return [

        trade

        for trade in TRADES

        if trade["status"] == "OPEN"

    ]


def get_open_trade(symbol: str):

    for trade in TRADES:

        if (

            trade["symbol"] == symbol

            and

            trade["status"] == "OPEN"

        ):

            return trade


    return None


# =========================================================
# ABRIR TRADE
# =========================================================

def open_simulated_trade(signal):


    global SIMULATION_CAPITAL


    symbol = signal["symbol"]


    if get_open_trade(symbol):

        return None


    if len(
        get_open_trades()
    ) >= MAX_OPEN_TRADES:

        return None


    score = signal["score"]


    if score < MIN_SCORE_TO_TRADE:

        return None


    # Utiliza 2% do capital como tamanho simulado
    position_value = (

        SIMULATION_CAPITAL
        *
        (
            TRADE_RISK_PERCENT
            /
            100
        )

    )


    trade = {

        "id": len(TRADES) + 1,

        "symbol": symbol,

        "side": signal["signal"],

        "entry": signal["entry"],

        "stop": signal["stop"],

        "target": signal["target"],

        "score": score,

        "confidence": signal["confidence"],

        "risk_reward": signal["risk_reward"],

        "position_value": round(
            position_value,
            2
        ),

        "status": "OPEN",

        "opened_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "closed_at": None,

        "exit_price": None,

        "result": None,

        "profit_percent": 0,

        "profit_value": 0

    }


    TRADES.append(
        trade
    )


    return trade


# =========================================================
# FECHAR TRADE
# =========================================================

def close_trade(

    trade,

    exit_price,

    result

):


    global SIMULATION_CAPITAL


    entry = float(
        trade["entry"]
    )


    if trade["side"] == "BUY":

        profit_percent = (

            (
                exit_price
                -
                entry
            )

            /
            entry

        ) * 100


    else:

        profit_percent = (

            (
                entry
                -
                exit_price
            )

            /
            entry

        ) * 100


    profit_value = (

        trade["position_value"]

        *

        profit_percent

        /

        100

    )


    trade["exit_price"] = round(

        exit_price,

        8

    )


    trade["profit_percent"] = round(

        profit_percent,

        4

    )


    trade["profit_value"] = round(

        profit_value,

        2

    )


    trade["status"] = "CLOSED"

    trade["result"] = result

    trade["closed_at"] = datetime.now(

        timezone.utc

    ).isoformat()


    SIMULATION_CAPITAL += profit_value


# =========================================================
# MONITOR
# =========================================================

def monitor_trades():

    while True:


        try:


            open_trades = get_open_trades()


            for trade in open_trades:


                current_price = get_current_price(

                    trade["symbol"]

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


                # BUY

                if side == "BUY":


                    if current_price <= stop:

                        close_trade(

                            trade,

                            current_price,

                            "LOSS"

                        )


                    elif current_price >= target:

                        close_trade(

                            trade,

                            current_price,

                            "WIN"

                        )


                # SELL

                elif side == "SELL":


                    if current_price >= stop:

                        close_trade(

                            trade,

                            current_price,

                            "LOSS"

                        )


                    elif current_price <= target:

                        close_trade(

                            trade,

                            current_price,

                            "WIN"

                        )


        except Exception as error:

            print(

                "Erro monitor:",

                error

            )


        time.sleep(

            MONITOR_INTERVAL

        )


# =========================================================
# THREAD MONITOR
# =========================================================

trade_monitor = threading.Thread(

    target=monitor_trades,

    daemon=True

)


trade_monitor.start()


# =========================================================
# ROTAS
# =========================================================

@app.get("/")
def home():

    return {

        "status": "online",

        "service": "Crypto Radar",

        "mode": "simulation",

        "symbols": len(SYMBOLS),

        "interval": INTERVAL,

        "capital": SIMULATION_CAPITAL

    }


@app.get("/price/{symbol}")
def price(symbol: str):


    current_price = get_current_price(

        symbol

    )


    if current_price is None:

        raise HTTPException(

            status_code=400,

            detail="Não foi possível consultar a moeda"

        )


    return {

        "symbol": symbol.upper(),

        "price": current_price

    }


@app.get("/radar/{symbol}")
def radar(symbol: str):


    result = analyze_symbol(

        symbol.upper()

    )


    if result is None:

        return {

            "symbol": symbol.upper(),

            "opportunity": False,

            "message": "Nenhuma oportunidade encontrada",

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


            result = analyze_symbol(

                symbol

            )


            if result:

                opportunities.append(

                    result

                )


        except Exception:

            continue


    opportunities.sort(

        key=lambda item: item["score"],

        reverse=True

    )


    return {

        "total_analyzed": analyzed,

        "total_opportunities": len(

            opportunities

        ),

        "opportunities": opportunities,

        "interval": INTERVAL

    }


@app.post("/trade/{symbol}")
def create_trade(symbol: str):


    signal = analyze_symbol(

        symbol.upper()

    )


    if signal is None:

        raise HTTPException(

            status_code=400,

            detail="Nenhum sinal disponível"

        )


    trade = open_simulated_trade(

        signal

    )


    if trade is None:

        return {

            "opened": False,

            "message": "Operação não aberta"

        }


    return {

        "opened": True,

        "trade": trade

    }


@app.post("/auto-scan")
def auto_scan():


    opened_trades = []


    for symbol in SYMBOLS:


        try:


            signal = analyze_symbol(

                symbol

            )


            if signal is None:

                continue


            trade = open_simulated_trade(

                signal

            )


            if trade:

                opened_trades.append(

                    trade

                )


        except Exception:

            continue


    return {

        "opened": len(

            opened_trades

        ),

        "trades": opened_trades,

        "open_trades": len(

            get_open_trades()

        )

    }


@app.get("/trades/open")
def open_trades_route():

    return {

        "total": len(

            get_open_trades()

        ),

        "trades": get_open_trades()

    }


@app.get("/trades")
def all_trades():

    return {

        "total": len(

            TRADES

        ),

        "trades": TRADES

    }


@app.get("/statistics")
def statistics_route():


    closed = [

        trade

        for trade in TRADES

        if trade["status"] == "CLOSED"

    ]


    wins = [

        trade

        for trade in closed

        if trade["result"] == "WIN"

    ]


    losses = [

        trade

        for trade in closed

        if trade["result"] == "LOSS"

    ]


    win_rate = 0


    if len(closed) > 0:

        win_rate = (

            len(wins)
            /
            len(closed)

        ) * 100


    total_profit = sum(

        trade["profit_value"]

        for trade in closed

    )


    return {

        "initial_capital": INITIAL_CAPITAL,

        "current_capital": round(

            SIMULATION_CAPITAL,

            2

        ),

        "open_trades": len(

            get_open_trades()

        ),

        "closed_trades": len(

            closed

        ),

        "wins": len(

            wins

        ),

        "losses": len(

            losses

        ),

        "win_rate": round(

            win_rate,

            2

        ),

        "total_profit": round(

            total_profit,

            2

        )

    }


@app.post("/reset")
def reset():


    global SIMULATION_CAPITAL


    TRADES.clear()


    SIMULATION_CAPITAL = INITIAL_CAPITAL


    return {

        "status": "reset",

        "capital": SIMULATION_CAPITAL

    }


@app.get("/status")
def status():


    return {

        "status": "online",

        "capital": SIMULATION_CAPITAL,

        "symbols": len(

            SYMBOLS

        ),

        "open_trades": len(

            get_open_trades()

        ),

        "total_trades": len(

            TRADES

        ),

        "interval": INTERVAL

    }
