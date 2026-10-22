# Operational Runbook & Disaster Recovery — SOLANA PREDATOR

## 1. Operating Environment & Android Process Lifecycle

### Android / Termux / PRoot Limitations
- **Background Execution Limitation**: Android OS aggressive battery management (OOM Killer, Doze Mode, Phantom Process Killer) can suspend or terminate background PRoot and Termux daemon processes without warning.
- **Process Persistence Strategy**:
  - Acquire Termux wakelock: `termux-wake-lock`.
  - Disable battery optimization for Termux in Android OS settings.
  - Run backend inside a `tmux` or `screen` session.
- **Automatic Recovery Procedure**:
  - SQLite WAL mode ensures database integrity is preserved even during immediate process kills.
  - Upon process restart, `PaperAccounting.reconcile_on_startup()` restores active positions and recalculates equity.

---

## 2. Standard Service Commands

### Starting the Backend Daemon
```bash
cd /root/solana_predator
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Running Backend Tests
```bash
cd /root/solana_predator
pytest -v backend/tests/
```

### Running Live Ingestion Smoke Test
```bash
python3 /root/solana_predator/backend/scripts/live_smoke_test.py
```

### Serving Web Terminal Locally
```bash
cd /root/solana_predator/frontend
python3 -m http.server 8080 --directory build/web
```
Access via web browser at: `http://localhost:8080` (or `http://<device-ip>:8080`).

---

## 3. Disaster Recovery & Troubleshooting

### Incident: WebSocket Connection Lost
- **Symptom**: Terminal banner displays red `DISCONNECTED` indicator.
- **Resolution**:
  - Check if backend is alive: `curl http://localhost:8000/api/health`.
  - `WebSocketService` will automatically reconnect with a 3-second bounded backoff.
  - If backend host changed, update via the **Config & Risk** tab.

### Incident: Database Lock or Corruption
- **Symptom**: `sqlite3.OperationalError: database is locked`.
- **Resolution**:
  - Check for dangling locks: `fuser /root/solana_predator/solana_predator.db`.
  - Re-run migrations: `python3 -c "from backend.database.migrations import apply_migrations; apply_migrations('/root/solana_predator/solana_predator.db')"`.
