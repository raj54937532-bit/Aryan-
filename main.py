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
load_dotenv()
BINANCE_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_API_SECRET")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ===== INIT CLIENTS =====
binance = Client(BINANCE_KEY, BINANCE_SECRET)
bot = Bot(token=TG_TOKEN)

# ===== SETTINGS & TRACKER =====
crypto = ["BTCUSDT", "ETHUSDT"]
forex = ["EURUSD=X", "GBPUSD=X"]
stocks = ["RELIANCE.NS", "TCS.NS", "AAPL", "TSLA"]
CANDLES = 100
last_signals = {}  # Duplicate signals rokne ke liye

# ===== RSI CALCULATION =====
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ===== DATA FETCHING =====
def get_binance_data(symbol, interval="1h"):
    k = binance.get_klines(symbol=symbol, interval=interval, limit=CANDLES)
    df = pd.DataFrame(k, columns=["t","o","h","l","c","v","ct","qav","tr","tbv","tq","i"])
    df = df[["o","h","l","c","v"]].astype(float)
    return df

def get_yfinance_data(symbol):
    df = yf.download(symbol, period="10d", interval="1h", progress=False)
    if df.empty: return None
    df = df.tail(CANDLES)
    # Handle possible Multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].rename(columns={"Open":"o","High":"h","Low":"l","Close":"c","Volume":"v"})
    return df

def liquidity_levels(df):
    swing_high = df["h"].rolling(5, center=True).max().iloc[-3]
    swing_low = df["l"].rolling(5, center=True).min().iloc[-3]
    return swing_high, swing_low

# ===== CALCULATE SIGNALS WITH FILTERS =====
def calc_signals(df, symbol):
    price = df["c"].iloc[-1]
    ema50 = df["c"].ewm(span=50).mean().iloc[-1]
    rsi_series = calculate_rsi(df["c"])
    rsi_val = rsi_series.iloc[-1]
    
    swing_high, swing_low = liquidity_levels(df)
    vol = df["v"].iloc[-1]

    # Strategy: EMA for Trend + RSI for exhaustion
    bias = None
    if price > ema50 and rsi_val < 70:
        bias = "LONG"
    elif price < ema50 and rsi_val > 30:
        bias = "SHORT"

    # Anti-Spam Check: Check if same bias already sent
    if bias == last_signals.get(symbol) or bias is None:
        return None

    last_signals[symbol] = bias # Update Tracker
    
    # Risk Management (1:2 RR)
    entry = price
    sl = swing_low if bias=="LONG" else swing_high
    risk = abs(entry - sl)
    tp = entry + (2 * risk) if bias=="LONG" else entry - (2 * risk)

    return entry, sl, tp, swing_high, swing_low, vol, rsi_val, ema50, bias

# ===== PLOT CHART =====
def plot_chart(df, swing_high, swing_low, ema50, symbol):
    plt.figure(figsize=(10,6))
    plt.plot(df["c"], label="Price", color="blue", linewidth=1)
    plt.axhline(swing_high, color="red", linestyle="--", alpha=0.5, label="Liq High")
    plt.axhline(swing_low, color="green", linestyle="--", alpha=0.5, label="Liq Low")
    plt.plot(df["c"].ewm(span=50).mean(), color="magenta", label="EMA50")
    plt.title(f"{symbol} Analysis")
    plt.legend()
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

# ===== MAIN LOOP =====
print("Bot starting... Monitoring Markets.")
while True:
    try:
        for sym in crypto + forex + stocks:
            df = get_binance_data(sym) if sym in crypto else get_yfinance_data(sym)
            if df is None: continue

            signal_data = calc_signals(df, sym)
            
            if signal_data:
                entry, sl, tp, sh, slw, vol, rsi, ema, bias = signal_data
                chart = plot_chart(df, sh, slw, ema, sym)
                
                msg = f"""
🚀 *NEW {bias} SIGNAL* 🚀
━━━━━━━━━━━━━━
📈 *Market:* `{sym}`
🎯 *Entry:* `{entry:.2f}`
🛑 *SL:* `{sl:.2f}`
💰 *TP:* `{tp:.2f}`
━━━━━━━━━━━━━━
📊 *Technical Stats:*
• RSI (14): `{rsi:.2f}`
• EMA 50: `{ema:.2f}`
• Vol: `{vol:,.0f}`
━━━━━━━━━━━━━━
"""
                bot.send_photo(chat_id=CHAT_ID, photo=chart, caption=msg, parse_mode="Markdown")
                print(f"Signal sent for {sym}")

        time.sleep(600)  # Check every 10 mins

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
        