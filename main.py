import os, numpy as np, yfinance as yf
from binance.client import Client
from telegram import Bot
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# Keys load
BINANCE_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_API_SECRET")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Clients init
binance = Client(BINANCE_KEY, BINANCE_SECRET)
bot = Bot(token=TG_TOKEN)

# Symbols list
crypto = ["BTCUSDT", "ETHUSDT"]
metals = ["BTCUSDT"]  # Binance me gold/silver direct nahi, proxy crypto/USDT hi milega
forex = ["EURUSD=X", "GBPUSD=X"]
stocks = ["RELIANCE.NS", "TCS.NS", "AAPL", "TSLA"]

def get_binance_klines(sym, tf="1h", limit=50):
    k = binance.get_klines(symbol=sym, interval=tf, limit=limit)
    df = pd.DataFrame(k, columns=["t","o","h","l","c","v","ct","qav","tr","tbv","tq","i"])
    df = df[["o","h","l","c","v"]].astype(float)
    return df

def get_forex_stock_price(sym):
    d = yf.download(sym, period="5d", interval="1h", progress=False)
    if d.empty: return None
    return float(d["Close"].iloc[-1])

def find_liquidity_levels(df):
    swing_high = df["h"].rolling(5, center=True).max().iloc[-3]
    swing_low = df["l"].rolling(5, center=True).min().iloc[-3]
    return swing_high, swing_low

def analyze_symbol(sym, source="binance"):
    if source=="binance":
        df = get_binance_klines(sym)
        price = df["c"].iloc[-1]
        ema50 = df["c"].ewm(span=50).mean().iloc[-1]
        high, low = find_liquidity_levels(df)
        vol = df["v"].iloc[-1]

    else:
        price = get_forex_stock_price(sym)
        if price is None: return
        df = yf.download(sym, period="5d", interval="1h", progress=False)
        high, low = find_liquidity_levels(df)
        vol = float(df["Volume"].iloc[-1]) if "Volume" in df else 0
        ema50 = float(df["Close"].ewm(span=50).mean().iloc[-1])

    # Condition logic
    bias = "LONG" if price > ema50 else "SHORT"
    entry = price
    sl = low if bias=="LONG" else high
    target = entry + (entry - sl)*2 if bias=="LONG" else entry - (sl - entry)*2

    msg = f"""
🔥 PRO TRADER SIGNAL 🔥
Market: {sym}
Direction: {bias}
Entry: {entry:.2f}
Stop-Loss: {sl:.2f}
Target: {target:.2f}
Liquidity High: {high:.2f}
Liquidity Low: {low:.2f}
Volume: {vol:.2f}
EMA50: {ema50:.2f}
"""
    bot.send_message(chat_id=CHAT_ID, text=msg)

# Loop markets
def run_bot():
    for s in crypto:
        analyze_symbol(s, "binance")

    for s in forex:
        analyze_symbol(s, "yahoo")

    for s in stocks:
        analyze_symbol(s, "yahoo")

    bot.send_message(chat_id=CHAT_ID, text="✅ Bot cycle complete. Next update soon…")

run_bot()