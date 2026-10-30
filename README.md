# Zerodha AI Financial Intelligence Platform — quick prototype

## Run on Windows
1. Install Python 3.11+ from https://www.python.org/downloads/ and tick **Add Python to PATH**.
2. Extract this ZIP.
3. Open the extracted folder in File Explorer. Click the address bar, type `cmd`, press Enter.
4. Run:
   ```bat
   py -m pip install -r requirements.txt
   py -m streamlit run app.py
   ```
5. Open the local URL printed in the terminal (usually http://localhost:8501).

CSV columns: `Stock`, `Sector`, `Quantity`, `Buy Price`, `Current Price`.

This is a demo with illustrative sample values. It does not connect to Zerodha, live market data, an LLM API, or MCP. Not financial advice.
