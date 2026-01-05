import os, time, numpy as np, requests
from telegram import Bot
from binance.client import Client

# ===== Keys (Replit/Server Secrets se aayengi) =====
BINANCE_API_KEY = os.getenv("HxY77uw1Nd5baY1lDSCsT9g2aQlBpgwbMPtXLSL3QcJvyKYa1WzAj0eORZRwcoze")
BINANCE_API_SECRET = os.getenv("auIWypWUMOXCBsuedaXo1IxcbDKoriDhQ718cJhgMft3NACwOwcEtnE4Gu2VgbM5")
TELEGRAM_TOKEN = os.getenv("8533843459:AAFahxEIhkIbwTEvDCa1SZVpIaeKi6NS8Jo")
CHAT_ID = os.getenv("7128570212")

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
bot = Bot(token=TELEGRAM_TOKEN)

CANDLES = 50
INTERVAL = "5m"
SYMBOL = "BTCUSDT"

# EMA 50
def ema(arr, period=50):
    alpha = 2/(period+1)
    e = [arr[0]]
    for p in arr[1:]:
        e.append(alpha*p + (1-alpha)*e[-1])
    return np.array(e)

# Support/Resistance
def sr(highs, lows):
    return highs.max(), lows.min()

# Liquidity sweep logic
def liquidity_sr_signal(closes, highs, lows, vols):
    price = closes[-1]
    liq_high = highs[-10:].max()
    liq_low  = lows[-10:].min()
    avg_vol  = vols[-10:].mean()
    vol_now  = vols[-1]
    e50 = ema(closes, 50)[-1]

    if price > liq_high and price > e50 and vol_now > avg_vol:
        signal="BUY"
        sl=liq_low
        tp=price + 2*(price-sl)
    elif price < liq_low and price < e50 and vol_now > avg_vol:
        signal="SELL"
        sl=liq_high
        tp=price - 2*(sl-price)
    else:
        signal="HOLD"
        sl=tp=None

    return signal, price, sl, tp, liq_low, liq_high

# TradingView se price (Forex/Indian market)
def get_tv_price(symbol):
    url = "https://scanner.tradingview.com/crypto/scan"
    payload = {"symbols":{"tickers":[symbol]}}
    try:
        r = requests.post(url, json=payload).json()
        return float(r['data'][0]['d'][0])
    except:
        return None

# Data fetch
def get_data():
    closes, highs, lows, vols = get_candles(SYMBOL)
    return closes, highs, lows, vols

def get_candles(sym):
    data = client.get_klines(symbol=sym, interval=INTERVAL, limit=CANDLES)
    closes = np.array([float(k[4]) for k in data])
    highs  = np.array([float(k[2]) for k in data])
    lows   = np.array([float(k[3]) for k in data])
    vols   = np.array([float(k[5]) for k in data])
    return closes, highs, lows, vols

last = None

while True:
    closes, highs, lows, vols = get_candles("BTCUSDT")
    signal, entry, sl, tp, liq_low, liq_high = liquidity_sr_signal(highs, lows, closes, vols)

    if signal != "HOLD" and signal != last:
        last = signal
        msg = f"""
📊 *Pro Trading Signal*
━━━━━━━━━━━━━━━━
🔥 *Signal:* {signal}
🎯 *Entry:* {entry:.2f}
🛑 *SL:* {sl:.2f}
💰 *TP (1:2 RR):* {tp:.2f}
📍 *Liquidity Support:* {liq_low:.2f}
📍 *Liquidity Resistance:* {liq_high:.2f}
━━━━━━━━━━━━━━━━
🤖 *Bot by: Aryan*
"""
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        print("Sent:", msg)

    time.sleep(10)