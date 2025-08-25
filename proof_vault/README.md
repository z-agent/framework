## Proof Vault

Curated, pluggable demos you can run and deploy. Each demo links to a minimal, production-ready path using what already exists in this repo, plus optional external integrations.

### Index
- Trading (ivishX, external) → see `trading_ivishx.md`
- Streaming Chat (Claude Code–style) → uses `/chat` endpoints documented in `STREAMING_API_README.md`
- Linear + GitHub Review → see `demos/linear_agents_demo.py` and server endpoints `/github/*`
- Solana Ops/Swarm → see `src/webapp/pages/SolanaOperations.js` and `src/client/jito_demo.py`
- Market Intelligence → see `demos/market-intelligence-demo.py`
- Natural Language Agent Generation → server endpoints `/generate_*_natural_language`
- Web3 Automation → see `demos/web3_automation_demo.py`

### Quick Start: API Server
```bash
python run_api.py
# API: http://localhost:8000, Docs: http://localhost:8000/docs
```

### Deploy (Docker)
```bash
docker build -f Dockerfile.prod -t zara-framework:prod .
docker run -p 8000:8000 --env-file ./env.production.template zara-framework:prod
```

### Next
- Start with `trading_ivishx.md` to run the external trading strategy and prepare a deployable demo.
- Frontend can consume streaming chat via `/chat/session/{id}/stream` (EventSource).






