import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
from google import genai

st.set_page_config(
    page_title="Zerodha AI Financial Intelligence",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Zerodha AI Financial Intelligence Platform")
st.caption("Educational prototype • Sample portfolio data • Not investment advice")

# --------------------------------------------------
# 1. PORTFOLIO DATA
# --------------------------------------------------

sample = pd.DataFrame([
    {"Stock": "RELIANCE", "Sector": "Energy", "Quantity": 10, "Buy Price": 2500, "Current Price": 2620},
    {"Stock": "TCS", "Sector": "IT", "Quantity": 8, "Buy Price": 3800, "Current Price": 3920},
    {"Stock": "INFY", "Sector": "IT", "Quantity": 15, "Buy Price": 1450, "Current Price": 1510},
    {"Stock": "HDFCBANK", "Sector": "Banking", "Quantity": 12, "Buy Price": 1600, "Current Price": 1550},
    {"Stock": "ITC", "Sector": "FMCG", "Quantity": 20, "Buy Price": 420, "Current Price": 445},
])

st.sidebar.header("Portfolio holdings")
st.sidebar.caption("Use this uploader only for holdings CSV.")

f = st.sidebar.file_uploader(
    "Upload holdings CSV (optional)",
    type=["csv"],
    key="holdings"
)

if f:
    try:
        h = pd.read_csv(f)
        required = {"Stock", "Sector", "Quantity", "Buy Price", "Current Price"}

        if not required.issubset(h.columns):
            st.sidebar.error("Incorrect holdings CSV format.")
            h = sample.copy()

    except Exception:
        h = sample.copy()
else:
    h = sample.copy()

for c in ["Quantity", "Buy Price", "Current Price"]:
    h[c] = pd.to_numeric(h[c], errors="coerce")

h = h.dropna(
    subset=["Quantity", "Buy Price", "Current Price"]
).copy()

h["Invested"] = h["Quantity"] * h["Buy Price"]
h["Current Value"] = h["Quantity"] * h["Current Price"]
h["P&L"] = h["Current Value"] - h["Invested"]

h["Return %"] = np.where(
    h["Invested"] != 0,
    h["P&L"] / h["Invested"] * 100,
    0
).round(2)

st.header("1. Portfolio overview")
st.caption("Illustrative sample holdings unless a valid holdings CSV is uploaded.")

inv = h["Invested"].sum()
val = h["Current Value"].sum()
pnl = h["P&L"].sum()
ret = pnl / inv * 100 if inv else 0

a, b, c, d = st.columns(4)

a.metric("Invested", f"₹{inv:,.0f}")
b.metric("Current value", f"₹{val:,.0f}")
c.metric("Profit / Loss", f"₹{pnl:,.0f}", f"{ret:+.2f}%")
d.metric("Holdings", str(len(h)))

l, r = st.columns(2)

with l:
    st.plotly_chart(
        px.pie(
            h.groupby("Sector", as_index=False)["Current Value"].sum(),
            names="Sector",
            values="Current Value",
            hole=.4,
            title="Allocation by sector"
        ),
        use_container_width=True
    )

with r:
    st.plotly_chart(
        px.bar(
            h,
            x="Stock",
            y="P&L",
            color="P&L",
            title="Profit / loss by stock"
        ),
        use_container_width=True
    )

st.dataframe(
    h[[
        "Stock", "Sector", "Quantity", "Buy Price",
        "Current Price", "Invested", "Current Value",
        "P&L", "Return %"
    ]],
    use_container_width=True,
    hide_index=True
)

# --------------------------------------------------
# 2. HISTORICAL STOCK DATA
# --------------------------------------------------

st.divider()
st.header("2. Historical stock data analysis (OHLCV)")

st.write(
    "Upload ALL_5_STOCKS_5Y_DAILY.csv or an individual "
    "CSV from your stock_csv folder."
)

hist_file = st.file_uploader(
    "Upload historical stock CSV",
    type=["csv"],
    key="history"
)

historical_context = "No historical stock CSV has been uploaded."

def norm(x):
    return str(x).strip().lower().replace(" ", "_").replace("-", "_")

if hist_file:
    try:
        raw = pd.read_csv(hist_file)
        cmap = {norm(c): c for c in raw.columns}

        datecol = next(
            (cmap[k] for k in ["date", "datetime", "timestamp"] if k in cmap),
            None
        )

        closecol = next(
            (cmap[k] for k in ["close", "adj_close", "adjclose"] if k in cmap),
            None
        )

        tickercol = next(
            (cmap[k] for k in ["ticker", "symbol", "stock"] if k in cmap),
            None
        )

        if datecol is None or closecol is None:
            st.error("Could not find Date and Close columns.")

        else:
            x = raw.copy()
            x["_date"] = pd.to_datetime(x[datecol], errors="coerce")
            x["_close"] = pd.to_numeric(x[closecol], errors="coerce")

            x = x.dropna(
                subset=["_date", "_close"]
            ).sort_values("_date")

            x["_ticker"] = (
                x[tickercol].astype(str)
                if tickercol
                else os.path.splitext(hist_file.name)[0]
            )

            tickers = sorted(x["_ticker"].unique())

            selected = st.multiselect(
                "Select stocks",
                tickers,
                default=tickers[:min(5, len(tickers))]
            )

            x = x[x["_ticker"].isin(selected)].copy()

            if not x.empty:
                st.subheader("Historical closing prices")

                st.plotly_chart(
                    px.line(
                        x,
                        x="_date",
                        y="_close",
                        color="_ticker",
                        labels={
                            "_date": "Date",
                            "_close": "Close price",
                            "_ticker": "Stock"
                        }
                    ),
                    use_container_width=True
                )

                x["_indexed"] = x.groupby("_ticker")["_close"].transform(
                    lambda s: s / s.iloc[0] * 100
                )

                st.subheader("Performance comparison (start = 100)")

                st.plotly_chart(
                    px.line(
                        x,
                        x="_date",
                        y="_indexed",
                        color="_ticker",
                        labels={
                            "_date": "Date",
                            "_indexed": "Indexed value",
                            "_ticker": "Stock"
                        }
                    ),
                    use_container_width=True
                )

                rows = []

                for ticker, g in x.groupby("_ticker"):
                    g = g.sort_values("_date")

                    if len(g) < 2:
                        continue

                    daily = g["_close"].pct_change().dropna()

                    yrs = max(
                        (g["_date"].iloc[-1] - g["_date"].iloc[0]).days / 365.25,
                        0.01
                    )

                    total = (
                        g["_close"].iloc[-1] /
                        g["_close"].iloc[0] - 1
                    ) * 100

                    cagr = (
                        (g["_close"].iloc[-1] /
                         g["_close"].iloc[0]) ** (1 / yrs) - 1
                    ) * 100 if g["_close"].iloc[0] > 0 else np.nan

                    vol = (
                        daily.std() * np.sqrt(252) * 100
                        if len(daily) > 1 else np.nan
                    )

                    dd = (
                        g["_close"] / g["_close"].cummax() - 1
                    ) * 100

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

                    st.dataframe(
                        metrics_df,
                        use_container_width=True,
                        hide_index=True
                    )

                    historical_context = metrics_df.to_string(index=False)

                st.caption(
                    "Metrics use the uploaded Close column. "
                    "Historical results do not predict future performance."
                )

    except Exception as e:
        st.error(f"Could not read/analyse this CSV: {e}")

else:
    st.info(
        "Upload your combined five-stock CSV here to view "
        "historical charts and risk/return metrics."
    )

# --------------------------------------------------
# 3. GEMINI AI CHATBOT
# --------------------------------------------------

st.divider()
st.header("3. 🤖 AI Financial Assistant")

st.write(
    "Ask questions about your portfolio and uploaded historical stock data."
)

# Read API key securely from Streamlit Secrets
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    gemini_api_key = None

if not gemini_api_key:
    st.warning(
        "Gemini API key not found. Add GEMINI_API_KEY "
        "in your Streamlit app's Secrets settings."
    )

else:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display previous chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_question = st.chat_input(
        "Ask something about your portfolio..."
    )

    if user_question:
        with st.chat_message("user"):
            st.markdown(user_question)

        portfolio_context = h[
            ["Stock", "Sector", "Quantity", "Invested",
             "Current Value", "P&L", "Return %"]
        ].to_string(index=False)

        conversation = ""

        for message in st.session_state.chat_history[-8:]:
            conversation += (
                f'{message["role"]}: {message["content"]}\n'
            )

        prompt = f"""
You are an educational AI financial assistant for a portfolio
intelligence prototype.

Answer in simple, clear language.

Use only the portfolio and historical information supplied below.
If information is missing, clearly say so. Do not invent stock prices,
news, market events, or financial figures.

Do not claim to have live market data or a live Zerodha connection.
Do not guarantee returns or present your answer as personalised
professional financial advice.

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
                        model="gemini-2.5-flash",
                        contents=prompt
                    )

                    answer = response.text
                    st.markdown(answer)

            st.session_state.chat_history.append({
                "role": "user",
                "content": user_question
            })

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer
            })

        except Exception as e:
            st.error(f"Gemini error: {e}")

    if st.button("Clear chat"):
        st.session_state.chat_history = []
        st.rerun()

# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "Educational prototype only: no live Zerodha connection, "
    "live market feed, MCP server, or trade execution. "
    "AI responses are informational and not investment advice."
)
