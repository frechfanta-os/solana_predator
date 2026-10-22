# SOLANA PREDATOR — Moteur d'Apprentissage et d'Évaluation (Learning Engine)

## 1. Objectif et Principes Fondamentaux

Le **Learning Engine** a pour mission d'évaluer scientifiquement et empiriquement les performances prédictives des agents décisionnels de **SOLANA PREDATOR**, sans jamais recourir à des seuils inventés ni souffrir de biais de rétro-regard (lookahead bias).

### Principes Clés :
1. **Zéro Biais Temporel (Strict Time Splitting)** : Les décisions sont triées dans l'ordre chronologique strict de leur horodatage source (`decision_timestamp`). Aucun événement futur ne peut fuiter dans les jeux d'entraînement ou de validation.
2. **Évaluation Out-of-Sample Réelle** : Toute nouvelle stratégie candidate est testée sur un split de validation distinct avant d'être candidate au déploiement.
3. **Comptabilité Réaliste** : Prise en compte systématique des frais d'exécution simulés (0.50% aller-retour) et du slippage dans le calcul du PnL net.

---

## 2. Partitionnement Temporel (`TemporalSplitter`)

Le module `backend/learning/temporal_split.py` applique un découpage chronologique strict :

```
Temps (t) ─────────────────────────────────────────────────────────────►
[======== JEU D'ENTRAÎNEMENT (60%) ========][== VALIDATION (20%) ==][== TEST HORS-ÉCHANTILLON (20%) ==]
t_0                                        t_train_end             t_val_end                          t_now
```

- **Invariant** : `max(t_train) < min(t_validation)` et `max(t_validation) < min(t_test)`.
- Validé par le test unitaire `test_strict_temporal_split_zero_lookahead`.

---

## 3. Critères d'Évaluation des Décisions (`DecisionOutcome`)

Pour chaque décision prise par le CHIEF au prix d'entrée $P_{entry}$ avec un horizon temporel $H$ (ex: 900s), le système observe les cours effectifs $[P_{t}]_{t \in [t_{dec}, t_{dec} + H]}$ :

| Métrique | Définition & Formule | Condition de Succès |
|---|---|---|
| **Achat Correct (`is_correct`)** | Le cours atteint $P_{cible}$ avant de toucher $P_{invalidation}$ | $\max(P) \ge P_{cible} \land \min(P) > P_{invalidation}$ |
| **Faux Positif (`is_false_positive`)** | Le cours touche le seuil d'invalidation ou termine en perte | $\min(P) \le P_{invalidation} \lor P_{final} < P_{entry}$ |
| **Vrai Négatif (`is_true_negative`)** | PASS/VETO alors que l'actif a baissé ou stagné ($< +5\%$) | $\max(P) < 1.05 \times P_{entry}$ |
| **Rendement Net Simulé** | $PnL_{net} = \frac{P_{final} - P_{entry}}{P_{entry}} \times 100 - Fee_{roundtrip}$ | Déduction systématique de 0.50% de frais |
| **Max Drawdown Simulé** | $\max(0, \frac{P_{entry} - \min(P)}{P_{entry}} \times 100)$ | Baisse maximale subie pendant la position |
| **MAE Erreur Prévision** | $|P_{cible} - \max(P)|$ | Écart absolu entre cible théorique et sommet atteint |

---

## 4. Attribution et Segmentation des Performances

Le moteur ventile les métriques selon plusieurs axes :
1. **Par Agent** : Score de contribution et taux de précision individuel (VET, SCAN, WHALE, QUANT, SKEPTIC).
2. **Par Version de Stratégie** : Comparaison rigoureuse de versions concurrentes (ex: `v1.1.0-consensus` vs `v1.2.0-candidate`).
3. **Par Tranche de Liquidité** : Détection des anomalies d'exécution sur les micro-pools ($<\$10k$, $\$10k-\$50k$, $>\$50k$).

---

## 5. Simulateur d'Optimisation de Stratégies (`StrategyOptimizer`)

Le module `backend/learning/optimizer.py` permet de tester des modifications de règles (ex: seuil de confiance minimal relevé à 0.85, multiplicateur d'objectif à 1.20) :
- Les simulations sont exécutées exclusivement sur le split `VALIDATION`.
- Aucun paramètre de production actif n'est modifié sans validation humaine et benchmark persistant dans la table `strategy_benchmarks`.
