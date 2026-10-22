# SOLANA PREDATOR — Système Indépendant de Contrôle des Risques (Independent Risk System)

## 1. Principe d'Indépendance Absolue

Le composant `IndependentRiskGuard` (`backend/live/independent_risk.py`) constitue la dernière ligne de défense infranchissable du système.

### Règles d'Inviolabilité :
- **Strictement découplé des modèles d'agents et de tout LLM** : Aucun agent (y compris le CHIEF) ne peut assouplir, ignorer ou contourner les seuils de risque configurés.
- **Fail-Safe par Défaut** : Toute panne RPC, donnée périmée, anomalie de format ou dépassement de seuil entraîne immédiatement le rejet de la proposition (`RISK_REJECTED`).
- **Traçabilité Exhaustive** : Chaque évaluation donne lieu à l'insertion immédiate des résultats dans la table SQLite `risk_audit_log`.

---

## 2. Les 13 Contrôles Indépendants Obligatoires

| # | Nom du Contrôle | Seuil Invariable | Conduite en cas de Dépassement |
|---|---|---|---|
| **1** | `EMERGENCY_KILL_SWITCH` | Désactivé (`False`) | **Blocage immédiat de toutes les opérations** |
| **2** | `MINT_VALIDITY` | Base58 valide (32-44 caractères), non système | Rejet si adresse malformée ou programme système |
| **3** | `NETWORK_VERIFICATION` | `mainnet-beta` strictement | Rejet si réseau incompatible ou testnet |
| **4** | `DATA_FRESHNESS` | $\le 30.0$ secondes | Rejet si les cours de marché sont obsolètes |
| **5** | `QUOTE_EXPIRATION` | Validité de devis $\le 15.0$ secondes | Rejet si le devis a expiré |
| **6** | `MAX_TRADE_AMOUNT` | $\le 1.50$ SOL par transaction | Rejet pour limiter l'exposition unitaire |
| **7** | `SOL_BALANCE_AND_RENT_RESERVE` | Solde $\ge Amount + Fee + 0.05$ SOL | Rejet pour préserver l'exemption de rente |
| **8** | `MAX_SLIPPAGE_BOUND` | $\le 250$ bps ($2.5\%$) | Rejet si le glissement de prix est excessif |
| **9** | `MIN_POOL_LIQUIDITY` | $\ge \$5,000$ USD | Rejet sur les micro-pools illiquides |
| **10** | `FEE_ESTIMATION_BOUND` | Frais prioritaires $\le 0.01$ SOL | Rejet si anomalie de frais réseau |
| **11** | `TRANSACTION_INSTRUCTION_INSPECTION` | Instructions Raydium/Token autorisées | Rejet si drains non autorisés ou payload altéré |
| **12** | `DOUBLE_SUBMISSION_GUARD` | Nonce unique par fenêtre de 10s | Rejet anti-rejeu et prévention du double-clic |
| **13** | `DATA_CONSISTENCY` | Sorties minimales attendues $> 0$ | Rejet si quantité de tokens nulle ou négative |

---

## 3. Dispositif d'Arrêt d'Urgence (Emergency Kill Switch)

Le Kill Switch global permet à un opérateur administrateur d'interrompre instantanément toutes les créations de propositions et les diffusions de transactions sans éteindre le terminal.

### API de Contrôle :
- **Activation** : `POST /api/live/kill-switch` avec `{ "active": true, "reason": "Forte volatilité anormale détectée" }`.
- **Désactivation** : `POST /api/live/kill-switch` avec `{ "active": false }`.
- **Effet Immédiat** : Le contrôle #1 échoue systématiquement avec le message *"Emergency kill-switch is currently active"*.

---

## 4. Audit Trail et Persistance (`risk_audit_log`)

Chaque passage d'une proposition dans l'audit génère 13 enregistrements détaillés :
- `proposal_id` : Identifiant unique de la proposition auditée.
- `check_name` : Nom du contrôle parmi les 13 ci-dessus.
- `passed` : 1 (Succès) ou 0 (Échec).
- `threshold_val` : Seuil théorique appliqué.
- `observed_val` : Valeur empirique constatée.
- `timestamp` : Horodatage exact de l'audit.
- `details_json` : Justification contextuelle et motif de rejet éventuel.

Accessible pour consultation et reporting via l'endpoint `/api/live/risk-audit`.
