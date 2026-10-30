import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
from datetime import datetime, timezone
import yfinance as yf
from google import genai

st.set_page_config(page_title="Zerodha AI Financial Intelligence", page_icon="📈", layout="wide")
st.title("📈 Zerodha AI Financial Intelligence Platform")
st.caption("Educational prototype • Market data may be delayed • Not investment advice")

# Yahoo Finance symbols for common NSE stocks. Add mappings as needed.
TICKER_MAP = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "INFOSYS": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "ITC": "ITC.NS",
}

@st.cache_data(ttl=300, show_spinner=False)
def get_latest_prices(stocks):
    """Return the latest available daily Close from Yahoo Finance, not a live quote."""
    prices = {}
    errors = {}
    for stock in stocks:
        clean_stock = str(stock).strip().upper()
        ticker = TICKER_MAP.get(clean_stock)
        if not ticker and clean_stock.endswith(".NS"):
            ticker = clean_stock
        if not ticker:
            errors[clean_stock] = "No Yahoo Finance ticker mapping is configured."
            continue
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            if hist.empty or "Close" not in hist:
                errors[clean_stock] = "No recent daily price returned."
                continue
            close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
            if close.empty:
                errors[clean_stock] = "No valid closing price returned."
                continue
            prices[clean_stock] = float(close.iloc[-1])
        except Exception as exc:
            errors[clean_stock] = str(exc)[:180]
    return prices, errors

# --------------------------------------------------
# 1. PORTFOLIO DATA
# --------------------------------------------------
sample = pd.DataFrame([
    {"Stock": "RELIANCE", "Sector": "Energy", "Quantity": 10, "Buy Price": 2500},
    {"Stock": "TCS", "Sector": "IT", "Quantity": 8, "Buy Price": 3800},
    {"Stock": "INFY", "Sector": "IT", "Quantity": 15, "Buy Price": 1450},
    {"Stock": "HDFCBANK", "Sector": "Banking", "Quantity": 12, "Buy Price": 1600},
    {"Stock": "ITC", "Sector": "FMCG", "Quantity": 20, "Buy Price": 420},
])

st.sidebar.header("Portfolio holdings")
st.sidebar.caption("Upload your actual holdings CSV. Required columns: Stock, Sector, Quantity, Buy Price. Current Price is fetched separately.")
holdings_file = st.sidebar.file_uploader("Upload holdings CSV (optional)", type=["csv"], key="holdings")

using_sample = holdings_file is None
if holdings_file is not None:
    try:
        h = pd.read_csv(holdings_file)
        required = {"Stock", "Sector", "Quantity", "Buy Price"}
        if not required.issubset(h.columns):
            st.sidebar.error("CSV needs Stock, Sector, Quantity and Buy Price columns. Using illustrative sample holdings.")
            h = sample.copy()
            using_sample = True
    except Exception as exc:
        st.sidebar.error(f"Could not read holdings CSV: {exc}. Using illustrative sample holdings.")
        h = sample.copy()
        using_sample = True
else:
    h = sample.copy()

h["Stock"] = h["Stock"].astype(str).str.strip().str.upper()
for col in ["Quantity", "Buy Price"]:
    h[col] = pd.to_numeric(h[col], errors="coerce")
h = h.dropna(subset=["Stock", "Quantity", "Buy Price"]).copy()
h = h[h["Quantity"] > 0].copy()

if h.empty:
    st.error("No valid holdings found. Upload a CSV with valid Stock, Sector, Quantity and Buy Price values.")
    st.stop()

with st.spinner("Fetching latest available daily closing prices from Yahoo Finance..."):
    latest_prices, price_errors = get_latest_prices(tuple(sorted(h["Stock"].unique())))

h["Current Price"] = h["Stock"].map(latest_prices)
h["Invested"] = h["Quantity"] * h["Buy Price"]
h["Current Value"] = h["Quantity"] * h["Current Price"]
h["P&L"] = h["Current Value"] - h["Invested"]
h["Return %"] = np.where(
    h["Invested"].notna() & h["Current Price"].notna() & (h["Invested"] != 0),
    h["P&L"] / h["Invested"] * 100,
    np.nan
).round(2)

st.header("1. Portfolio overview")
if using_sample:
    st.warning("These are illustrative sample quantities and buy prices, not your real Zerodha holdings. Upload your actual holdings CSV for a meaningful portfolio calculation.")
else:
    st.caption("Buy prices and quantities come from your uploaded holdings file. Current prices come from Yahoo Finance daily data.")

priced = h["Current Price"].notna()
priced_count = int(priced.sum())
st.caption(f"Prices retrieved: {priced_count} of {len(h)} holdings. Data source: Yahoo Finance (unofficial; latest available daily close, may be delayed).")

if price_errors:
    with st.expander("Stocks with unavailable prices"):
        for stock, error in price_errors.items():
            st.write(f"**{stock}:** {error}")

if priced_count:
    st.caption("Last available daily closing price is shown, not a guaranteed real-time quote.")
    latest_date = datetime.now().strftime("%d %b %Y, %I:%M %p")
    st.caption(f"Checked at: {latest_date} (India local app time may differ from market data date).")

if priced_count == len(h):
    inv = h["Invested"].sum()
    val = h["Current Value"].sum()
    pnl = h["P&L"].sum()
    ret = pnl / inv * 100 if inv else 0
    a, b, c, d = st.columns(4)
    a.metric("Invested", f"₹{inv:,.2f}")
    b.metric("Current value", f"₹{val:,.2f}")
    c.metric("Profit / Loss", f"₹{pnl:,.2f}", f"{ret:+.2f}%")
    d.metric("Holdings priced", f"{priced_count}/{len(h)}")
else:
    st.warning("Portfolio totals are hidden until prices are available for every holding. This avoids presenting an incomplete total as accurate.")
    a, b, c = st.columns(3)
    a.metric("Invested", f"₹{h['Invested'].sum():,.2f}")
    b.metric("Holdings priced", f"{priced_count}/{len(h)}")
    c.metric("Holdings awaiting price", str(len(h) - priced_count))

if priced_count:
    chart_data = h.loc[priced].copy()
    l, r = st.columns(2)
    with l:
        st.plotly_chart(
            px.pie(chart_data.groupby("Sector", as_index=False)["Current Value"].sum(),
                   names="Sector", values="Current Value", hole=.4,
                   title="Allocation by sector (priced holdings)"),
            use_container_width=True
        )
    with r:
        st.plotly_chart(
            px.bar(chart_data, x="Stock", y="P&L", color="P&L",
                   title="Profit / loss by stock (priced holdings)"),
            use_container_width=True
        )

display_cols = ["Stock", "Sector", "Quantity", "Buy Price", "Current Price", "Invested", "Current Value", "P&L", "Return %"]
st.dataframe(h[display_cols], use_container_width=True, hide_index=True)
st.caption("A missing price is shown as blank. No hardcoded sample current prices are used.")

# --------------------------------------------------
# 2. HISTORICAL STOCK DATA
# --------------------------------------------------
st.divider()
st.header("2. Historical stock data analysis (OHLCV)")
st.write("Upload ALL_5_STOCKS_5Y_DAILY.csv or an individual CSV from your stock_csv folder.")
hist_file = st.file_uploader("Upload historical stock CSV", type=["csv"], key="history")
historical_context = "No historical stock CSV has been uploaded."

def norm(x):
    return str(x).strip().lower().replace(" ", "_").replace("-", "_")

if hist_file:
    try:
        raw = pd.read_csv(hist_file)
        cmap = {norm(c): c for c in raw.columns}
        datecol = next((cmap[k] for k in ["date", "datetime", "timestamp"] if k in cmap), None)
        closecol = next((cmap[k] for k in ["close", "adj_close", "adjclose"] if k in cmap), None)
        tickercol = next((cmap[k] for k in ["ticker", "symbol", "stock"] if k in cmap), None)

        if datecol is None or closecol is None:
            st.error("Could not find Date and Close columns. Upload a CSV generated by the stock-data helper.")
        else:
            x = raw.copy()
            x["_date"] = pd.to_datetime(x[datecol], errors="coerce")
            x["_close"] = pd.to_numeric(x[closecol], errors="coerce")
            x = x.dropna(subset=["_date", "_close"]).sort_values("_date")
            x["_ticker"] = x[tickercol].astype(str) if tickercol else os.path.splitext(hist_file.name)[0]
            tickers = sorted(x["_ticker"].unique())
            selected = st.multiselect("Select stocks", tickers, default=tickers[:min(5, len(tickers))])
            x = x[x["_ticker"].isin(selected)].copy()

            if not x.empty:
                st.subheader("Historical closing prices")
                st.plotly_chart(px.line(x, x="_date", y="_close", color="_ticker",
                                        labels={"_date": "Date", "_close": "Close price", "_ticker": "Stock"}),
                                use_container_width=True)
                x["_indexed"] = x.groupby("_ticker")["_close"].transform(lambda s: s / s.iloc[0] * 100)
                st.subheader("Performance comparison (start = 100)")
                st.plotly_chart(px.line(x, x="_date", y="_indexed", color="_ticker",
                                        labels={"_date": "Date", "_indexed": "Indexed value", "_ticker": "Stock"}),
                                use_container_width=True)
                rows = []
                for ticker, g in x.groupby("_ticker"):
                    g = g.sort_values("_date")
                    if len(g) < 2:
                        continue
                    daily = g["_close"].pct_change().dropna()
                    yrs = max((g["_date"].iloc[-1] - g["_date"].iloc[0]).days / 365.25, 0.01)
                    total = (g["_close"].iloc[-1] / g["_close"].iloc[0] - 1) * 100
                    cagr = ((g["_close"].iloc[-1] / g["_close"].iloc[0]) ** (1 / yrs) - 1) * 100 if g["_close"].iloc[0] > 0 else np.nan
                    vol = daily.std() * np.sqrt(252) * 100 if len(daily) > 1 else np.nan
                    dd = (g["_close"] / g["_close"].cummax() - 1) * 100
                    rows.append({
                        "Stock": ticker,
                        "Start date": g["_date"].min().date(),
                        "End date": g["_date"].max().date(),
                        "Rows": len(g),
                        "Total return %": round(total, 2),
                        "Annualized return (CAGR) %": round(cagr, 2),
                        "Annualized volatility %": round(vol, 2),
                        "Max drawdown %": round(dd.min(), 2)
                    })
                if rows:
                    metrics_df = pd.DataFrame(rows)
                    st.subheader("Historical risk and return")
                    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                    historical_context = metrics_df.to_string(index=False)
                st.caption("Metrics use the uploaded Close column. Historical results do not predict future performance.")
    except Exception as exc:
        st.error(f"Could not read/analyse this CSV: {exc}")
else:
    st.info("Upload your combined five-stock CSV here to view historical charts and risk/return metrics.")

# --------------------------------------------------
# 3. GEMINI AI CHATBOT
# --------------------------------------------------
st.divider()
st.header("3. 🤖 AI Financial Assistant")
st.write("Ask questions about your portfolio and uploaded historical stock data.")

try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    gemini_api_key = None

if not gemini_api_key:
    st.warning("Gemini API key not found. Add GEMINI_API_KEY in your Streamlit app's Secrets settings.")
else:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_question = st.chat_input("Ask something about your portfolio...")
    if user_question:
        with st.chat_message("user"):
            st.markdown(user_question)

        safe_h = h.copy()
        safe_h = safe_h.where(pd.notna(safe_h), None)
        portfolio_context = safe_h[["Stock", "Sector", "Quantity", "Invested", "Current Price", "Current Value", "P&L", "Return %"]].to_string(index=False)
        conversation = "\n".join(
            f'{m["role"]}: {m["content"]}' for m in st.session_state.chat_history[-8:]
        )
        prompt = f"""
You are an educational AI financial assistant for a portfolio intelligence prototype.
Answer clearly and simply. Use only the supplied portfolio and historical information.
If a price is missing, say it is unavailable. Never invent prices, news or market facts.
Do not claim to have live market data or a live Zerodha connection. Do not guarantee returns.
This is informational education, not personalised professional financial advice.

PORTFOLIO DATA:
{portfolio_context}

HISTORICAL ANALYSIS:
{historical_context}

PREVIOUS CONVERSATION:
{conversation}

USER QUESTION:
{user_question}
"""
        try:
            client = genai.Client(api_key=gemini_api_key)
            with st.chat_message("assistant"):
                with st.spinner("Gemini is analysing your question..."):
                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=prompt
                    )
                    answer = response.text or "Gemini returned an empty response. Please try again."
                    st.markdown(answer)

            st.session_state.chat_history.append({"role": "user", "content": user_question})
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        except Exception as exc:
            st.error(f"Gemini error: {exc}")

    if st.button("Clear chat"):
        st.session_state.chat_history = []
        st.rerun()

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.divider()
st.caption("Educational prototype only: no live Zerodha connection, official exchange feed, MCP server, or trade execution. Yahoo Finance data is unofficial and may be delayed. AI responses are informational and not investment advice.")
