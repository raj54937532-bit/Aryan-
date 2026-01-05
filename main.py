import os
import time
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from io import BytesIO
from binance.client import Client
from telegram import Bot
from dotenv import load_dotenv

# ===== LOAD ENV VARIABLES =====
load_dotenv()  # MUST be called before using os.getenv

BINANCE_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_API_SECRET")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ===== DEBUG PRINT KEYS =====
print("BINANCE_KEY =", BINANCE_KEY is not None)
print("BINANCE_SECRET =", BINANCE_SECRET is not None)
print("TG_TOKEN =", TG_TOKEN is not None)
print("CHAT_ID =", CHAT_ID is not None)

# ===== INIT CLIENTS =====
binance = Client(BINANCE_KEY, BINANCE_SECRET)
bot = Bot(token=TG_TOKEN)

# ===== MARKETS =====
crypto = ["BTCUSDT", "ETHUSDT"]
forex = ["EURUSD=X", "GBPUSD=X"]
stocks = ["RELIANCE.NS", "TCS.NS", "AAPL", "TSLA"]

CANDLES = 50  # Number of candles for calculations

# ===== FETCH BINANCE DATA =====
def get_binance_data(symbol, interval="1h"):
    k = binance.get_klines(symbol=symbol, interval=interval, limit=CANDLES)
    df = pd.DataFrame(k, columns=["t","o","h","l","c","v","ct","qav","tr","tbv","tq","i"])
    df = df[["o","h","l","c","v"]].astype(float)
    return df

# ===== FETCH YFINANCE DATA =====
def get_yfinance_data(symbol):
    df = yf.download(symbol, period="5d", interval="1h", progress=False)
    if df.empty:
        return None
    df = df.tail(CANDLES)
    df = df[["Open","High","Low","Close","Volume"]].rename(columns={"Open":"o","High":"h","Low":"l","Close":"c","Volume":"v"})
    return df

# ===== LIQUIDITY LEVELS =====
def liquidity_levels(df):
    swing_high = df["h"].rolling(5, center=True).max().iloc[-3]
    swing_low = df["l"].rolling(5, center=True).min().iloc[-3]
    return swing_high, swing_low

# ===== CALCULATE SIGNALS =====
def calc_signals(df):
    price = df["c"].iloc[-1]
    ema50 = df["c"].ewm(span=50).mean().iloc[-1]
    swing_high, swing_low = liquidity_levels(df)
    vol = df["v"].iloc[-1]

    bias = "LONG" if price > ema50 else "SHORT"
    entry = price
    sl = swing_low if bias=="LONG" else swing_high
    tp = entry + 2*(entry-sl) if bias=="LONG" else entry - 2*(sl-entry)

    return entry, sl, tp, swing_high, swing_low, vol, ema50, bias

# ===== PLOT CHART =====
def plot_chart(df, swing_high, swing_low, ema50):
    plt.figure(figsize=(10,5))
    plt.plot(df["c"], label="Close", color="blue")
    plt.plot(df["h"], color="green", alpha=0.3)
    plt.plot(df["l"], color="red", alpha=0.3)
    plt.axhline(swing_high, color="orange", linestyle="--", label="Liquidity High")
    plt.axhline(swing_low, color="yellow", linestyle="--", label="Liquidity Low")
    plt.plot(df["c"].ewm(span=50).mean(), color="magenta", linestyle="-", label="EMA50")
    plt.title("Liquidity + EMA50 Chart")
    plt.legend()
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

# ===== SEND TELEGRAM SIGNAL =====
def send_signal(symbol, entry, sl, tp, swing_high, swing_low, vol, ema50, bias, chart_buf):
    msg = f"""
🔥 PRO TRADING SIGNAL 🔥
Market: {symbol}
Direction: {bias}
Entry: {entry:.2f}
SL: {sl:.2f}
TP: {tp:.2f}
Liquidity High: {swing_high:.2f}
Liquidity Low: {swing_low:.2f}
Volume: {vol:.2f}
EMA50: {ema50:.2f}
"""
    bot.send_photo(chat_id=CHAT_ID, photo=chart_buf, caption=msg)

# ===== MAIN LOOP =====
while True:
    try:
        for sym in crypto + forex + stocks:
            if sym in crypto:
                df = get_binance_data(sym)
            else:
                df = get_yfinance_data(sym)
                if df is None:
                    continue

            entry, sl, tp, swing_high, swing_low, vol, ema50, bias = calc_signals(df)
            chart_buf = plot_chart(df, swing_high, swing_low, ema50)
            send_signal(sym, entry, sl, tp, swing_high, swing_low, vol, ema50, bias, chart_buf)

        time.sleep(600)  # 10 min interval

    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")
        time.sleep(60)