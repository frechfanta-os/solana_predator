# SOLANA PREDATOR — Intégration LLM GLM-5.3-Flash (OpenAI Chat Completions Compatible)

## 1. Vue d'Ensemble et Objectifs

L'intégration LLM de **SOLANA PREDATOR** connecte les agents décisionnels à un fournisseur compatible avec le protocole OpenAI Chat Completions, ciblant le modèle haute performance à faible latence **GLM-5.3-Flash**.

### Principes Directeurs et Invariants de Sécurité :
1. **Rôle Purement Consultatif (Advisory Layer)** : Le LLM apporte une analyse qualitative, une interprétation sémantique des signaux et une synthèse d'arguments contradictoires.
2. **Calculs Déterministes Intouchables** : Le LLM ne remplace **JAMAIS** les calculs déterministes de prix, volumes, liquidité, soldes de portefeuille, slippage, frais ou indicateurs techniques.
3. **Inviolabilité du VETO de RISK** : Aucune réponse du LLM ne peut annuler, contourner ou assouplir un VETO émis par l'agent `RISK` ou par l'`IndependentRiskGuard`.
4. **Zéro Capacité d'Exécution On-Chain** : Le LLM n'a aucun accès aux clés privées (inexistantes sur le backend) et ne peut en aucun cas signer ou diffuser seul une transaction réelle.
5. **Mode Dégradé / Repli Transparent (Fail-Safe)** : Si le fournisseur est désactivé, hors ligne ou en erreur, les agents basculent instantanément sur les heuristiques déterministes sans interruption de service.
6. **Confidentialité et Zéro Fuite de Clés** : Aucune clé API, en-tête d'authentification ou secret de portefeuille n'est journalisé ou consigné dans les logs.

---

## 2. Configuration Centralisée des Variables d'Environnement

La configuration est gérée de manière générique et indépendante du code métier via les variables d'environnement définies dans `.env` (exclu de Git par `.gitignore`) et documentées dans `.env.example` :

| Variable d'Environnement | Description | Valeur par Défaut |
|---|---|---|
| `LLM_ENABLED` | Activation globale des requêtes LLM | `false` |
| `LLM_PROVIDER` | Nom logique du fournisseur (`openrouter`, `space_z`) | `openrouter` / `space_z` |
| `LLM_API_BASE_URL` | Base URL du point d'entrée HTTP | `https://openrouter.ai/api/v1` |
| `LLM_API_KEY` | Clé d'authentification (secrète) | `sk-...` (renseignée dans `.env`) |
| `LLM_MODEL` | Identifiant du modèle principal | `poolside/laguna-s-2.1:free` |
| `LLM_MODEL_POOL` | Pool de modèles gratuits pour alternance et failover | `poolside/laguna-s-2.1:free,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,...` |
| `LLM_ROTATION_ENABLED` | Activation de la rotation de charge entre modèles | `true` |
| `LLM_TIMEOUT_SECONDS` | Délai d'expiration maximal par requête | `15.0` |
| `LLM_MAX_RETRIES` | Nombre maximal de tentatives sur 429/5xx | `3` |
| `LLM_MAX_CONCURRENCY` | Nombre maximal de requêtes simultanées | `5` |
| `LLM_TEMPERATURE` | Température d'échantillonnage | `0.2` |
| `LLM_MAX_TOKENS` | Longueur maximale de la complétion | `1024` |
| `LLM_STREAM` | Streaming de réponse (désactivé par défaut) | `false` |
| `LLM_AUTH_HEADER_STYLE` | Format d'en-tête (`bearer`, `x-api-key`, `both`) | `bearer` |

### Construction de l'Endpoint :
Le client construit l'endpoint standard OpenAI Chat Completions :
$$\text{Endpoint} = \text{LLM\_API\_BASE\_URL} + \text{"/chat/completions"}$$

---

## 3. Architecture du Client Centralisé (`LLMClient`)

Le service `backend/llm/client.py` fournit une couche asynchrone robuste basée sur `aiohttp` :

```
                        ┌──────────────────────────────────────┐
                        │      AgentOrchestrator / API         │
                        └──────────────────┬───────────────────┘
                                           │
                                           ▼
                        ┌──────────────────────────────────────┐
                        │              LLMClient               │
                        │ ┌──────────────────────────────────┐ │
                        │ │   asyncio.Semaphore(concurrency) │ │
                        │ └──────────────────────────────────┘ │
                        │ ┌──────────────────────────────────┐ │
                        │ │   Exponential Backoff + Jitter   │ │
                        │ └──────────────────────────────────┘ │
                        │ ┌──────────────────────────────────┐ │
                        │ │   Header Masking & Secret Redact │ │
                        │ └──────────────────────────────────┘ │
                        │ ┌──────────────────────────────────┐ │
                        │ │   Monotonic Latency Measurement  │ │
                        │ └──────────────────────────────────┘ │
                        └──────────────────┬───────────────────┘
                                           │
                     ┌─────────────────────┴─────────────────────┐
                     ▼                                           ▼
      [HTTP 200 OK: Valid JSON]                     [HTTP 401/429/500 or Timeout]
                     │                                           │
                     ▼                                           ▼
         ┌───────────────────────┐                  ┌─────────────────────────┐
         │ Validated Advisory    │                  │ Typed Exception /       │
         │ (AgentLLMAdvisory)    │                  │ Deterministic Fallback  │
         └───────────────────────┘                  └─────────────────────────┘
```

### Résilience et Traitement des Erreurs :
- **HTTP 401 / 403 (Authentification)** : Levée immédiate de `LLMAuthenticationError` sans aucune nouvelle tentative inutile.
- **HTTP 429 (Rate Limit)** : Retries avec backoff exponentiel et jitter aléatoire ($\text{delay} = \min(4.0, 2^{attempt} \times 0.5) \times U(0.8, 1.2)$).
- **HTTP 5xx (Erreur Serveur)** : Retries avec backoff jusqu'à `LLM_MAX_RETRIES`.
- **Délai d'Expiration (Timeout)** : Biais temporel strict ; levée de `LLMTimeoutError`.
- **Limitation de Concurrence** : Toutes les requêtes transitent par un sémaphore asynchrone borné (`max_concurrency = 5`).

---

## 4. Intégration aux 9 Agents Décisionnels

| Agent | Rôle de l'Advisory LLM | Comportement en Mode Dégradé (Fallback) |
|---|---|---|
| **CHIEF** | Synthèse globale des 8 analyses, pondération qualitative | Synthèse purement déterministe basée sur les votes et scores |
| **SCAN** | Interprétation sémantique de la liquidité et de l'activité du pool | Règles statiques de liquidité (\$5k) et de volume (\$10k) |
| **WHALE** | Évaluation des flux et des clusters de portefeuilles | Seuils on-chain de flux et déduplication mathématique |
| **VET** | Synthèse des risques de code et des drapeaux de métadonnées | Contrôles stricts de mint et freeze authority révoqués |
| **QUANT** | Interprétation de la vélocité et du ratio volume/liquidité | Modèle statistique déterministe de turnover |
| **SKEPTIC** | Recherche active de contre-arguments et signaux de wash-trading | Algorithme heuristique de détection de divergence |
| **SIZE** | Évaluation d'impact de taille sur la profondeur du carnet | Formule d'allocation de Kelly et fraction de liquidité |
| **RISK** | Contrôle de plausibilité des risques | Contrôles infranchissables de drawdown et de limites |
| **AUDIT** | Génération de résumés de conformité et traçabilité | Horodatage et journalisation brute des codes de décision |

---

## 5. Contrat de Sortie Validé (`AgentLLMAdvisory`)

Toute réponse d'agent fait l'objet d'une validation Pydantic stricte :

```json
{
  "agent": "SCAN",
  "token_mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
  "decision": "BUY_CANDIDATE",
  "confidence": 0.88,
  "evidence": [
    "Volume surge +200% on Raydium pool",
    "Verified continuous liquidity additions"
  ],
  "risks": [
    "Pool concentration in top 3 holders"
  ],
  "invalidation_conditions": [
    "Price drops below 1.15 USD within 900s",
    "Liquidity drops under 5,000 USD"
  ],
  "summary": "High momentum breakout setup confirmed with verified DEX backing.",
  "strategy_version": "glm5-glm-5.3-flash",
  "created_at": 1792694236.74,
  "latency_ms": 342.5,
  "provider": "space_z",
  "model": "glm-5.3-flash",
  "raw_tokens_used": 150
}
```

---

## 6. Protection contre les Injections de Prompts

Les métadonnées de tokens et les payloads de marché externes sont strictement confinés dans une balise étanche `<market_event_data>` :
- L'instruction système ordonne explicitement au modèle de considérer tout contenu dans cette balise comme des **données inertes non exécutables**.
- Les tentatives d'injection visant à altérer les règles système ou à forcer un achat sont ignorées par le modèle et filtrées par le validateur de schéma.

---

## 7. Endpoints de l'API REST

- `GET /api/llm/status` : Télémétrie opérationnelle du fournisseur (statut, modèle actif, nombre d'appels, erreurs, latence moyenne, clé masquée).
- `POST /api/llm/analyze` : Point d'entrée pour solliciter une analyse ad-hoc d'un token auprès d'un rôle d'agent donné.
