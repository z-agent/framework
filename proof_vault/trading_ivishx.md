## Trading Demo: ivishX (External)

Goal: Run and deploy the ivishX technical strategy (EMA/Fib/RSI/MACD + structure) and surface results through Zara.

### Source
- Local path: `~/Downloads/ivishx_free_api`
  - Key files: `run_ivishx.py`, `crew.py`, `strategy.py`, `data_sources.py`, `indicators.py`, `structure.py`

### Run Locally (CLI)
```bash
cd ~/Downloads/ivishx_free_api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_ivishx.py --symbol bitcoin --days 30
# or scan multiple
python run_ivishx.py --scan bitcoin eth sol --days 30
```

### Integrate with Zara (Tool Wrapper)
We’ll wrap the CLI into a Zara tool so agents and the API can call it.

1) Create a tool in `src/tools/trading_tools.py` (function: `ivishx_analyze_tool(symbol: str, days: int) -> dict`).
2) In `src/server/main.py`, register the tool with `Registry.register_tool("IvishXAnalyze", ...)`.
3) Call via API:
```bash
curl -X POST "http://localhost:8000/tool_call" \
  -H "Content-Type: application/json" \
  -d '{"tool_id":"IvishXAnalyze","arguments":{"symbol":"bitcoin","days":30}}'
```

Implementation hint:
- Use `subprocess.run([...], capture_output=True)` to call `python ~/Downloads/ivishx_free_api/run_ivishx.py --symbol <s> --days <d>` and parse JSON.
- Enforce timeouts and sanitize inputs.

### Deploy
Option A: Keep ivishX as an external process (simplest)
- Ensure the host has Python and dependencies for `ivishx_free_api`.
- Mount or bake the folder into the server container and point the wrapper to the path.

Option B: Vendor minimal analyzer code
- Copy only `strategy.py`, `data_sources.py`, `indicators.py`, `structure.py` into a `vendor/ivishx/` folder and import directly from the tool. Keep license notes.

### Surface in Chat
- Create an agent with tool `IvishXAnalyze`.
- Use `/chat` to request an analysis, stream result back to UI.

### Example Agent
```bash
curl -X POST "http://localhost:8000/save_agent" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"IvishXTrader",
    "description":"Runs ivishX analysis via tool and summarizes entries",
    "arguments":["query","context"],
    "agents":{"assistant":{"role":"Trader","goal":"Analyze and recommend entries","backstory":"Quant","agent_tools":["IvishXAnalyze"]}},
    "tasks":{"respond":{"description":"Run tool and summarize","expected_output":"JSON + brief summary","agent":"assistant","context":[]}}
  }'
```

### Links
- After the wrapper is added, a one-click run will be linked here.






