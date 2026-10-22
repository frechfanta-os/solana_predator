# System Architecture — SOLANA PREDATOR

## 1. Architectural Overview

SOLANA PREDATOR is architected as an asynchronous, event-driven intelligence terminal decoupled into an autonomous backend processing daemon and a reactive frontend client.

```mermaid
flowchart TD
    subgraph MarketData [Market Data Layer]
        RPC[Solana Read-Only RPC] --> Ingest[Event Normalizer]
        DEX[DEX Screener REST] --> Ingest
        REPLAY[Deterministic Replay Provider] --> Ingest
    end

    subgraph CorePipeline [Low-Latency Event Pipeline]
        Ingest --> Deduplication[LRU / TTL Deduplicator]
        Deduplication --> EventBus[Bounded Async Event Bus]
        EventBus --> TokenRadar[Token Discovery Radar]
        EventBus --> WhaleEngine[Whale Intelligence Engine]
        TokenRadar --> MultiAgent[Multi-Agent Consensus Engine]
        WhaleEngine --> MultiAgent
    end

    subgraph MultiAgentEngine [Multi-Agent Analysis]
        MultiAgent --> VET[VET: Safety & Honeypot]
        MultiAgent --> SCAN[SCAN: Discovery & Volume]
        MultiAgent --> WHALE[WHALE: Accumulation Flow]
        MultiAgent --> QUANT[QUANT: Turnover & Uncertainty]
        MultiAgent --> SKEPTIC[SKEPTIC: Contrarian Risks]
        MultiAgent --> SIZE[SIZE: Position Allocator]
        MultiAgent --> RISK[RISK: Absolute Drawdown Veto]
        VET & SCAN & WHALE & QUANT & SKEPTIC & SIZE & RISK --> CHIEF[CHIEF: Consensus Synthesizer]
        CHIEF --> AUDIT[AUDIT: Calibration & SLA]
    end

    subgraph PaperBrokerage [Deterministic Paper Simulator]
        CHIEF --> PaperBroker[Isolated Paper Broker]
        PaperBroker --> Positions[Position Manager]
        Positions --> Accounting[Paper Accounting & WAL Store]
        Positions --> ExitMonitor[Continuous Exit Monitor]
        ExitMonitor --> PaperBroker
    end

    subgraph Interfaces [Distribution Layer]
        Accounting --> SQLite[(SQLite WAL Database)]
        Accounting --> FastApi[FastAPI REST API]
        EventBus --> WS[WebSocket Manager]
        FastApi & WS --> Flutter[Flutter Terminal Web / Android]
    end
```

---

## 2. Component Design Principles

### Decoupled Background Execution
The backend runs as a standalone Python 3.12+ `uvicorn` service. It does not depend on the Flutter frontend remaining connected or active. All persistent state resides in SQLite configured with Write-Ahead Logging (`WAL`), supporting atomic commits and instant crash recovery.

### Inviolable Risk Boundary
The `RISK` agent possesses unilateral veto power:
- If portfolio drawdown exceeds 15%, all new simulated buying is vetoed.
- If concurrent open positions reach the configured limit (default: 5), new candidates are vetoed.
- If the token is already actively held, duplicate allocations are vetoed.
- `CHIEF` cannot override a `RISK` veto under any circumstances.

### Strict Read-Only Security Model
The system does not import, store, or accept Solana private keys, seeds, or signers. The paper broker is completely separated from the on-chain networking adapters, eliminating any possibility of accidental mainnet funds transmission.
