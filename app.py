from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI(title="Binance Radar API", version="1.0.0")

BINANCE = "https://api.binance.com"

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
    return {**s.model_dump(), "risk_reward": rr, "mode": "simulado"}
