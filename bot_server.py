import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import yfinance as yf
import pandas as pd
import pytz

# Retrieve credentials securely from cloud environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
IST = pytz.timezone("Asia/Kolkata")

# Watchlist of liquid NSE stocks
NSE_UNIVERSE = [
    "SBIN.NS", "TATASTEEL.NS", "ASHOKLEY.NS", "BEL.NS", "BHEL.NS",
    "TATAPOWER.NS", "HINDALCO.NS", "COALINDIA.NS", "ONGC.NS", "NTPC.NS",
    "POWERGRID.NS", "CANBK.NS", "PNB.NS", "BANKBARODA.NS", "FEDERALBNK.NS",
    "IDFCFIRSTB.NS", "NATIONALUM.NS", "NMDC.NS", "SAIL.NS", "VEDL.NS",
    "HINDCOPPER.NS", "IRFC.NS", "RVNL.NS", "IREDA.NS", "SUZLON.NS",
    "ZOMATO.NS", "JIOFIN.NS", "MUTHOOTFIN.NS", "RECLTD.NS", "PFC.NS"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responds when you send /start on Telegram."""
    await update.message.reply_text(
        "🤖 *NSE Intraday AI Agent is Online!*\n\n"
        "Send me */scan* anytime during market hours to fetch live volume breakouts and top momentum picks for your ₹10,000 capital."
    )

async def scan_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches live data and scans the universe on demand when you type /scan."""
    await update.message.reply_text("🔍 Scanning live NSE tape and running VWAP + Volume filters...")
    
    try:
        # Download latest daily & intraday data
        daily_data = yf.download(NSE_UNIVERSE, period="1mo", interval="1d", group_by="ticker", progress=False, threads=True)
        intraday_data = yf.download(NSE_UNIVERSE, period="1d", interval="5m", group_by="ticker", progress=False, threads=True)
        
        candidates = []
        for ticker in NSE_UNIVERSE:
            try:
                df_d = daily_data[ticker].dropna()
                df_5m = intraday_data[ticker].dropna()
                if len(df_d) < 10 or len(df_5m) < 1:
                    continue

                prev_close = float(df_d["Close"].iloc[-2])
                avg_daily_vol = float(df_d["Volume"].tail(20).mean())
                if avg_daily_vol <= 0:
                    continue

                day_open = float(df_5m["Open"].iloc[0])
                total_vol_today = float(df_5m["Volume"].sum())
                
                typical_price = (df_5m["High"] + df_5m["Low"] + df_5m["Close"]) / 3.0
                vwap = float((typical_price * df_5m["Volume"]).sum() / total_vol_today) if total_vol_today > 0 else day_open

                last_bar = df_5m.iloc[-1]
                c_close = float(last_bar["Close"])
                c_vol = float(last_bar["Volume"])
                
                expected_5m_vol = avg_daily_vol / 75.0
                rvol_5m = c_vol / expected_5m_vol if expected_5m_vol > 0 else 0
                day_pct_change = ((c_close - prev_close) / prev_close) * 100.0

                # Basic filters
                if 50.0 <= c_close <= 1000.0 and 0.5 <= day_pct_change <= 6.0 and c_close >= vwap:
                    score = min(rvol_5m * 10.0, 50.0) + min(day_pct_change * 10.0, 50.0)
                    candidates.append({
                        "symbol": ticker.replace(".NS", ""),
                        "ltp": round(c_close, 2),
                        "vwap": round(vwap, 2),
                        "day_pct": round(day_pct_change, 2),
                        "rvol": round(rvol_5m, 1),
                        "score": round(score, 1)
                    })
            except Exception:
                continue

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_picks = candidates[:2]

        if not top_picks:
            await update.message.reply_text("⚠️ No stocks met the strict volume breakout criteria right now. Market may be consolidating.")
            return

        response_text = "🚀 *LATEST LIVE INTRADAY SCAN RESULTS*\n\n"
        for idx, p in enumerate(top_picks, 1):
            response_text += (
                f"*{idx}. {p['symbol']}* (Score: {p['score']}/100)\n"
                f"• LTP: ₹{p['ltp']} (+{p['day_pct']}% | VWAP: ₹{p['vwap']})\n"
                f"• Volume Surge: {p['rvol']}x normal\n\n"
            )
        response_text += "💡 *Reminder:* Use 2.5x safe sizing (₹25k exposure) and set your Stop-Loss immediately!"
        
        await update.message.reply_text(response_text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching market data: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan_market))
    print("Bot server is polling for Telegram messages...")
    app.run_polling()