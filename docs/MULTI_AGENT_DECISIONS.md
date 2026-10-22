# SOLANA PREDATOR — Architecture des Décisions Multi-Agents

## 1. Vue d'Ensemble

Le moteur décisionnel de **SOLANA PREDATOR** orchestre 9 agents spécialisés travaillant de concert pour analyser les événements du marché Solana en temps réel. Chaque décision d'investissement ou d'abstention est structurée, persistante, reproductible et horodatée.

```
                      ┌───────────────────────┐
                      │ NormalizedMarketEvent │
                      └───────────┬───────────┘
                                  │
    ┌────────────┬────────────┬───┴────────┬────────────┬────────────┐
    ▼            ▼            ▼            ▼            ▼            ▼
 ┌──────┐     ┌───────┐    ┌─────┐      ┌─────┐     ┌───────┐     ┌──────┐
 │ SCAN │     │ WHALE │    │ VET │      │QUANT│     │SKEPTIC│     │ SIZE │
 └──────┘     └───────┘    └─────┘      └─────┘     └───────┘     └──────┘
    │            │            │            │            │            │
    └────────────┼────────────┴────────────┼────────────┴────────────┘
                 │                         │
                 ▼                         ▼
            ┌─────────┐               ┌─────────┐
            │  RISK   │ ◄── VETO? ──► │  CHIEF  │
            └─────────┘               └────┬────┘
                                           │
                                           ▼
                                      ┌─────────┐
                                      │  AUDIT  │
                                      └────┬────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  ChiefConsensusRecord   │
                              │ (SQLite WAL Persistence)│
                              └─────────────────────────┘
```

---

## 2. Rôles et Responsabilités des 9 Agents

| Agent | Rôle Primaire | Critères Clés Analysés | Pouvoir de Décision |
|---|---|---|---|
| **SCAN** | Découverte & Liquidité | Pool liquidity > \$5,000, 24h Volume > \$10,000, paires actives | Signal favorable / défavorable |
| **WHALE** | Intelligence Portefeuilles | Détection d'accumulations vérifiées on-chain, clusters de wallets | Signal favorable / défavorable |
| **VET** | Sécurité Smart Contract | Freeze authority révoquée, mint authority renoncée, pas de honeypot | Signal favorable / défavorable |
| **QUANT** | Dynamique de Prix & Momentum | Ratio volume/liquidité, vélocité de prix, slippage estimé | Score quantitatif [0.0 - 1.0] |
| **SKEPTIC** | Contradiction & Esprit Critique | Recherche active d'anomalies, divergences wash-trading, dilution | Affaiblissement de conviction |
| **SIZE** | Dimensionnement du Risque | Calcul de taille de position optimale selon la liquidité | Montant suggéré en USD / SOL |
| **RISK** | Gardien du Risque Global | Drawdown maximal (15%), exposition cumulée, limites de positions | **VETO ABSOLU NON-CONTOURNABLE** |
| **CHIEF** | Synthèse Stratégique | Consolidation harmonique des 8 analyses, fixation des cibles | Décision finale (BUY / PASS / VETO) |
| **AUDIT** | Traçabilité & Conformité | Horodatage nanoseconde, latence par agent, journalisation SQLite | Enregistrement infalsifiable |

---

## 3. Contrat Décisionnel Structuré (`ChiefConsensusRecord`)

Toute décision générée par le CHIEF produit un enregistrement exhaustif répondant aux exigences strictes de traçabilité :

```json
{
  "consensus_id": "chief_6689cc096e82",
  "token_mint": "TokenMintMultiAgent11111111111111111111111",
  "token_symbol": "TOKEN",
  "data_timestamp": 1792694236.7399,
  "timestamp": 1792694236.7430,
  "final_decision": "BUY_CANDIDATE",
  "strategic_decision": "BUY_CANDIDATE",
  "is_risk_vetoed": false,
  "chief_reason": "APPROVED PAPER BUY: 2 buy signals, consensus score 0.77, allocation $500.00",
  "sources_used": ["SOLANA_RPC"],
  "favorable_signals": [
    "SCAN_LIQUIDITY_MET",
    "SCAN_VOLUME_OBSERVED",
    "QUANT_ACTIVE_TURNOVER_CONFIRMED",
    "QUANT_RATIO_1.60",
    "SKEPTIC_CLEARED_COUNTER_SIGNALS",
    "SIZE_CALCULATED_USD_500.00"
  ],
  "unfavorable_signals": [
    "VET_INTEGRITY_VERIFIED",
    "WHALE_NO_TRACKED_ACTIVITY",
    "RISK_CHECKS_PASSED"
  ],
  "confidence_score": 0.7725,
  "confidence_method": "MULTI_AGENT_WEIGHTED_HARMONIC",
  "invalidation_conditions": [
    "price_drop_exceeds_4.5%",
    "liquidity_collapse_below_5000_usd",
    "honeypot_or_freeze_authority_detected",
    "whale_rapid_distribution_detected",
    "evaluation_horizon_900s_elapsed"
  ],
  "identified_risks": [],
  "strategy_version": "v1.2.0-consensus",
  "expected_outcome": "+12.5% price advance within 900s horizon",
  "evaluation_horizon_sec": 900,
  "entry_price_usd": 1.25,
  "target_price_usd": 1.40625,
  "invalidation_price_usd": 1.19375,
  "recommended_position_usd": 500.0,
  "processing_total_latency_ms": 0.619
}
```

---

## 4. Propriétés Invariantes

1. **Reproductibilité Déterministe** : À événements et état de portefeuille identiques, l'orchestrateur produit exactement les mêmes signaux, scores et prix d'invalidation (validé par `test_decision_reproducibility`).
2. **Priorité Veto RISK** : Le CHIEF ne peut en aucun cas passer outre un VETO de RISK (validé par `test_risk_veto_blocks_decision`).
3. **Absence Totale de Clés Privées** : Aucun agent ne dispose d'un accès à des primitives de signature on-chain ou de gestion de clés privées.
4. **Persistance Immédiate** : Chaque consensus et chaque décision individuelle d'agent sont enregistrés dans les tables `chief_decisions` et `agent_decisions` via SQLite WAL.
