import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai

st.set_page_config(
    page_title="Zerodha AI Financial Intelligence",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Zerodha AI Financial Intelligence Platform")
st.caption("Educational prototype • Yahoo Finance prices may be delayed • Not investment advice")

# --------------------------------------------------
# MARKET DATA
# --------------------------------------------------

TICKER_MAP = {
    "RELIANCE": "RELIANCE.NS", "ONGC": "ONGC.NS",
    "NTPC": "NTPC.NS", "POWERGRID": "POWERGRID.NS",
    "TATAPOWER": "TATAPOWER.NS", "TCS": "TCS.NS",
    "INFY": "INFY.NS", "HCLTECH": "HCLTECH.NS",
    "WIPRO": "WIPRO.NS", "TECHM": "TECHM.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS", "KOTAKBANK": "KOTAKBANK.NS",
    "AXISBANK": "AXISBANK.NS", "BAJFINANCE": "BAJFINANCE.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS", "LICI": "LICI.NS",
    "MARUTI": "MARUTI.NS", "M&M": "M&M.NS",
    "TATAMOTORS": "TATAMOTORS.NS", "EICHERMOT": "EICHERMOT.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "DRREDDY": "DRREDDY.NS",
    "CIPLA": "CIPLA.NS", "ITC": "ITC.NS",
    "HINDUNILVR": "HINDUNILVR.NS", "NESTLEIND": "NESTLEIND.NS",
    "TITAN": "TITAN.NS", "ASIANPAINT": "ASIANPAINT.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS", "LT": "LT.NS",
    "TATASTEEL": "TATASTEEL.NS", "JSWSTEEL": "JSWSTEEL.NS",
    "BHARTIARTL": "BHARTIARTL.NS", "ADANIPORTS": "ADANIPORTS.NS"
}

@st.cache_data(ttl=900, show_spinner=False)
def get_latest_prices(stock_names):
    """Fetch latest available daily Close for supported NSE symbols."""
    prices = {}
    failed = []
    for stock in stock_names:
        ticker = TICKER_MAP.get(str(stock).strip().upper())
        if not ticker:
            failed.append(stock)
            continue
        try:
            data = yf.Ticker(ticker).history(
                period="5d", interval="1d",
                auto_adjust=False, actions=False
            )
            if data.empty or "Close" not in data:
                failed.append(stock)
                continue
            close = pd.to_numeric(data["Close"], errors="coerce").dropna()
            if close.empty:
                failed.append(stock)
            else:
                prices[stock] = float(close.iloc[-1])
        except Exception:
            failed.append(stock)
    return prices, failed

def normalise_column(value):
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")

# --------------------------------------------------
# 1. PORTFOLIO HOLDINGS
# --------------------------------------------------

st.sidebar.header("Portfolio holdings")
st.sidebar.caption(
    "Upload the generated 36-stock CSV or your own holdings CSV. "
    "Required columns: Stock, Sector, Quantity, Buy Price."
)
holdings_file = st.sidebar.file_uploader(
    "Upload holdings CSV", type=["csv"], key="holdings"
)

demo = pd.DataFrame([
    {"Stock": "RELIANCE", "Sector": "Energy", "Quantity": 10, "Buy Price": 2331.64},
    {"Stock": "TCS", "Sector": "IT", "Quantity": 5, "Buy Price": 3150},
    {"Stock": "INFY", "Sector": "IT", "Quantity": 15, "Buy Price": 1526},
    {"Stock": "HDFCBANK", "Sector": "Banking", "Quantity": 12, "Buy Price": 725},
    {"Stock": "ITC", "Sector": "FMCG", "Quantity": 20, "Buy Price": 328.78},
])

if holdings_file is not None:
    try:
        h = pd.read_csv(holdings_file)
        h.columns = [str(c).strip() for c in h.columns]
        required = {"Stock", "Sector", "Quantity", "Buy Price"}
        if not required.issubset(h.columns):
            st.sidebar.error(
                "CSV must contain Stock, Sector, Quantity and Buy Price. "
                "Please check the column headings."
            )
            h = demo.copy()
            using_demo = True
        else:
            using_demo = False
    except Exception as exc:
        st.sidebar.error(f"Could not read holdings CSV: {exc}")
        h = demo.copy()
        using_demo = True
else:
    h = demo.copy()
    using_demo = True

h["Stock"] = h["Stock"].astype(str).str.strip().str.upper()
h["Sector"] = h["Sector"].fillna("Unclassified").astype(str)
for col in ["Quantity", "Buy Price"]:
    h[col] = pd.to_numeric(h[col], errors="coerce")
h = h.dropna(subset=["Stock", "Quantity", "Buy Price"]).copy()
h = h[h["Stock"].ne("")].copy()

if using_demo:
    st.warning(
        "You are viewing illustrative demo holdings, not actual Zerodha holdings. "
        "Upload your generated CSV in the left sidebar to use the 35-stock dataset."
    )
elif "Reference Date" in h.columns:
    ref_dates = sorted(h["Reference Date"].dropna().astype(str).unique())
    if ref_dates:
        st.info(
            "Historical reference price file detected. Buy Price values are "
            f"the historical closing prices recorded for: {', '.join(ref_dates)}. "
            "Quantities are illustrative demo quantities."
        )

# Fetch prices for uploaded/demo portfolio stocks
stock_list = h["Stock"].drop_duplicates().tolist()
with st.spinner("Fetching latest available daily closing prices from Yahoo Finance..."):
    latest_prices, failed_prices = get_latest_prices(tuple(stock_list))

h["Current Price"] = h["Stock"].map(latest_prices)
h["Invested"] = h["Quantity"] * h["Buy Price"]
h["Current Value"] = h["Quantity"] * h["Current Price"]
h["P&L"] = h["Current Value"] - h["Invested"]
h["Return %"] = np.where(
    h["Invested"].ne(0),
    h["P&L"] / h["Invested"] * 100,
    np.nan
).round(2)

priced = h.dropna(subset=["Current Price"]).copy()
missing_stocks = h.loc[h["Current Price"].isna(), "Stock"].tolist()

st.header("1. Portfolio overview")
if not using_demo:
    st.caption("Portfolio based on the uploaded holdings file.")
else:
    st.caption("Illustrative sample portfolio.")

checked_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p")
st.caption(
    f"Prices retrieved: {len(priced)} of {len(h)} holdings. "
    "Source: Yahoo Finance (unofficial; latest available daily close, may be delayed)."
)
st.caption(f"Checked at: {checked_at} India time. Market data date may differ.")

if missing_stocks:
    st.warning(
        "No current price returned for: " + ", ".join(missing_stocks) +
        ". These holdings are retained but excluded from priced-value totals."
    )

total_invested = h["Invested"].sum()
priced_value = priced["Current Value"].sum()
priced_invested = priced["Invested"].sum()
priced_pnl = priced["P&L"].sum()
priced_return = priced_pnl / priced_invested * 100 if priced_invested else 0

if len(priced) == len(h) and len(h) > 0:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total invested", f"₹{total_invested:,.2f}")
    m2.metric("Current value", f"₹{priced_value:,.2f}")
    m3.metric("Profit / Loss", f"₹{priced_pnl:,.2f}", f"{priced_return:+.2f}%")
    m4.metric("Holdings priced", f"{len(priced)}/{len(h)}")
else:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total invested", f"₹{total_invested:,.2f}")
    m2.metric("Value of priced holdings", f"₹{priced_value:,.2f}")
    m3.metric("P&L of priced holdings", f"₹{priced_pnl:,.2f}", f"{priced_return:+.2f}%")
    m4.metric("Holdings priced", f"{len(priced)}/{len(h)}")

if not priced.empty:
    left, right = st.columns(2)
    with left:
        sector_data = priced.groupby("Sector", as_index=False)["Current Value"].sum()
        st.plotly_chart(
            px.pie(sector_data, names="Sector", values="Current Value",
                   hole=0.4, title="Allocation by sector (priced holdings)"),
            use_container_width=True
        )
    with right:
        st.plotly_chart(
            px.bar(priced, x="Stock", y="P&L", color="P&L",
                   title="Profit / loss by stock (priced holdings)"),
            use_container_width=True
        )

display_cols = [
    "Stock", "Sector", "Quantity", "Buy Price", "Current Price",
    "Invested", "Current Value", "P&L", "Return %"
]
if "Reference Date" in h.columns:
    display_cols.append("Reference Date")
st.dataframe(
    h[display_cols],
    use_container_width=True,
    hide_index=True
)
st.caption(
    "Historical Close is used as the reference Buy Price in the generated demo CSV. "
    "Demo quantities are not actual holdings. Yahoo Finance prices are not guaranteed live quotes."
)

if st.button("Refresh market prices"):
    get_latest_prices.clear()
    st.rerun()

# --------------------------------------------------
# 2. HISTORICAL STOCK DATA ANALYSIS
# --------------------------------------------------

st.divider()
st.header("2. Historical stock data analysis (OHLCV)")
st.write(
    "Upload ALL_5_STOCKS_5Y_DAILY.csv or individual historical stock CSV files."
)
hist_file = st.file_uploader(
    "Upload historical stock CSV", type=["csv"], key="history"
)
historical_context = "No historical stock CSV has been uploaded."

if hist_file:
    try:
        raw = pd.read_csv(hist_file)
        cmap = {normalise_column(c): c for c in raw.columns}
        datecol = next(
            (cmap[k] for k in ["date", "datetime", "timestamp"] if k in cmap), None
        )
        closecol = next(
            (cmap[k] for k in ["close", "adj_close", "adjclose"] if k in cmap), None
        )
        tickercol = next(
            (cmap[k] for k in ["ticker", "symbol", "stock"] if k in cmap), None
        )
        if datecol is None or closecol is None:
            st.error("Could not find Date and Close columns in this historical CSV.")
        else:
            x = raw.copy()
            x["_date"] = pd.to_datetime(x[datecol], errors="coerce")
            x["_close"] = pd.to_numeric(x[closecol], errors="coerce")
            x = x.dropna(subset=["_date", "_close"]).sort_values("_date")
            x["_ticker"] = (
                x[tickercol].astype(str) if tickercol
                else os.path.splitext(hist_file.name)[0]
            )
            tickers = sorted(x["_ticker"].unique())
            selected = st.multiselect(
                "Select stocks", tickers,
                default=tickers[:min(5, len(tickers))]
            )
            x = x[x["_ticker"].isin(selected)].copy()
            if not x.empty:
                st.subheader("Historical closing prices")
                st.plotly_chart(
                    px.line(x, x="_date", y="_close", color="_ticker",
                            labels={"_date": "Date", "_close": "Close price",
                                    "_ticker": "Stock"}),
                    use_container_width=True
                )
                x["_indexed"] = x.groupby("_ticker")["_close"].transform(
                    lambda s: s / s.iloc[0] * 100
                )
                st.subheader("Performance comparison (start = 100)")
                st.plotly_chart(
                    px.line(x, x="_date", y="_indexed", color="_ticker",
                            labels={"_date": "Date", "_indexed": "Indexed value",
                                    "_ticker": "Stock"}),
                    use_container_width=True
                )
                rows = []
                for ticker, g in x.groupby("_ticker"):
                    g = g.sort_values("_date")
                    if len(g) < 2:
                        continue
                    daily = g["_close"].pct_change().dropna()
                    years = max(
                        (g["_date"].iloc[-1] - g["_date"].iloc[0]).days / 365.25,
                        0.01
                    )
                    total = (g["_close"].iloc[-1] / g["_close"].iloc[0] - 1) * 100
                    cagr = (
                        (g["_close"].iloc[-1] / g["_close"].iloc[0]) ** (1 / years) - 1
                    ) * 100 if g["_close"].iloc[0] > 0 else np.nan
                    volatility = daily.std() * np.sqrt(252) * 100 if len(daily) > 1 else np.nan
                    drawdown = (g["_close"] / g["_close"].cummax() - 1) * 100
                    rows.append({
                        "Stock": ticker,
                        "Start date": g["_date"].min().date(),
                        "End date": g["_date"].max().date(),
                        "Rows": len(g),
                        "Total return %": round(total, 2),
                        "Annualized return (CAGR) %": round(cagr, 2),
                        "Annualized volatility %": round(volatility, 2),
                        "Max drawdown %": round(drawdown.min(), 2)
                    })
                if rows:
                    metrics_df = pd.DataFrame(rows)
                    st.subheader("Historical risk and return")
                    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                    historical_context = metrics_df.to_string(index=False)
                st.caption(
                    "Metrics use the uploaded Close column. Historical results do not "
                    "predict future performance."
                )
    except Exception as exc:
        st.error(f"Could not read/analyse this CSV: {exc}")
else:
    st.info("Upload your historical stock CSV here to view historical charts and metrics.")

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
    st.warning("Gemini API key not found. Add GEMINI_API_KEY in Streamlit app Secrets.")
else:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask something about your portfolio...")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        portfolio_context = h[
            ["Stock", "Sector", "Quantity", "Buy Price", "Current Price",
             "Invested", "Current Value", "P&L", "Return %"]
        ].to_string(index=False)

        prompt = f"""
You are an educational AI financial assistant.
Answer clearly and simply. Use only the data below; do not invent prices,
news, or figures. If current price is missing, say it is unavailable.
Do not claim live Zerodha access or guarantee returns. This is not
personalised professional financial advice.

PORTFOLIO:
{portfolio_context}

HISTORICAL ANALYSIS:
{historical_context}

USER QUESTION:
{question}
"""
        try:
            client = genai.Client(api_key=gemini_api_key)
            with st.chat_message("assistant"):
                with st.spinner("Gemini is analysing your question..."):
                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=prompt
                    )
                    answer = response.text or "Gemini returned an empty response."
                    st.markdown(answer)
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer}
            )
        except Exception as exc:
            st.error(f"Gemini error: {exc}")

    if st.button("Clear chat"):
        st.session_state.chat_history = []
        st.rerun()

st.divider()
st.caption(
    "Educational prototype only: no live Zerodha connection, official exchange feed, "
    "MCP server, or trade execution. Market data is unofficial and may be delayed. "
    "AI responses are informational and not investment advice."
)
