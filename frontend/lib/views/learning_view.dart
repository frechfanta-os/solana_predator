import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class LearningView extends ConsumerStatefulWidget {
  const LearningView({super.key});

  @override
  ConsumerState<LearningView> createState() => _LearningViewState();
}

class _LearningViewState extends ConsumerState<LearningView> {
  bool _isEvaluating = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(terminalControllerProvider).fetchLearningMetrics();
    });
  }

  Future<void> _runEvaluation() async {
    setState(() => _isEvaluating = true);
    final success = await ref.read(terminalControllerProvider).triggerLearningEvaluation();
    setState(() => _isEvaluating = false);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? "Learning evaluation completed successfully!" : "Evaluation failed"),
          backgroundColor: success ? AppTheme.predatorGreen : AppTheme.dangerRed,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final metrics = ref.watch(learningMetricsProvider);

    final totalDecisions = metrics["total_decisions_evaluated"] ?? 0;
    final accuracyRate = ((metrics["correct_decisions_rate"] ?? 0.0) as num).toDouble() * 100.0;
    final falsePositiveRate = ((metrics["false_positive_rate"] ?? 0.0) as num).toDouble() * 100.0;
    final simulatedReturn = ((metrics["simulated_net_return_pct"] ?? 0.0) as num).toDouble();
    final maxDrawdown = ((metrics["max_simulated_drawdown_pct"] ?? 0.0) as num).toDouble();
    final maePrice = ((metrics["mean_absolute_error_price"] ?? 0.0) as num).toDouble();

    final byAgent = (metrics["results_by_agent"] as Map<String, dynamic>?) ?? {};
    final byStrategy = (metrics["results_by_strategy"] as Map<String, dynamic>?) ?? {};
    final byTier = (metrics["results_by_liquidity_tier"] as Map<String, dynamic>?) ?? {};

    return Scaffold(
      backgroundColor: AppTheme.scaffoldBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with action
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "MEASURABLE LEARNING ENGINE",
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.predatorGreen),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "Empirical multi-agent decision evaluation across temporal splits without lookahead bias",
                        style: TextStyle(fontSize: 12, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  icon: _isEvaluating
                      ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                      : const Icon(Icons.psychology, size: 16),
                  label: Text(_isEvaluating ? "Evaluating..." : "Run Evaluation"),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.predatorGreen,
                    foregroundColor: Colors.black,
                  ),
                  onPressed: _isEvaluating ? null : _runEvaluation,
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Metrics Cards Layout (Wrap for responsiveness)
            LayoutBuilder(
              builder: (context, constraints) {
                final cardWidth = constraints.maxWidth > 900
                    ? (constraints.maxWidth - 50) / 6
                    : (constraints.maxWidth > 550 ? (constraints.maxWidth - 20) / 3 : constraints.maxWidth);
                return Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    SizedBox(width: cardWidth, child: _metricCard("Evaluated Decisions", "$totalDecisions", Icons.analytics, AppTheme.accentCyan)),
                    SizedBox(width: cardWidth, child: _metricCard("Accuracy Rate", "${accuracyRate.toStringAsFixed(1)}%", Icons.check_circle, AppTheme.predatorGreen)),
                    SizedBox(width: cardWidth, child: _metricCard("False Positive Rate", "${falsePositiveRate.toStringAsFixed(1)}%", Icons.warning, AppTheme.warningAmber)),
                    SizedBox(width: cardWidth, child: _metricCard("Simulated Net Return", "${simulatedReturn >= 0 ? '+' : ''}${simulatedReturn.toStringAsFixed(2)}%", Icons.trending_up, simulatedReturn >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed)),
                    SizedBox(width: cardWidth, child: _metricCard("Max Simulated DD", "${maxDrawdown.toStringAsFixed(1)}%", Icons.arrow_downward, AppTheme.dangerRed)),
                    SizedBox(width: cardWidth, child: _metricCard("Price Forecast MAE", "\$${maePrice.toStringAsFixed(4)}", Icons.compare_arrows, AppTheme.textMuted)),
                  ],
                );
              },
            ),
            const SizedBox(height: 24),

            // Breakdowns Row
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Agent Performance Attribution
                Expanded(
                  flex: 3,
                  child: Card(
                    color: AppTheme.cardBg,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("AGENT PERFORMANCE ATTRIBUTION", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.accentCyan)),
                          const Divider(height: 20),
                          if (byAgent.isEmpty)
                            const Text("No agent outcome data available", style: TextStyle(color: AppTheme.textMuted, fontSize: 12))
                          else
                            ...byAgent.entries.map((e) {
                              final data = e.value as Map<String, dynamic>;
                              final pPower = ((data["predictive_power"] ?? data["veto_accuracy"] ?? 0.8) as num).toDouble() * 100.0;
                              return Padding(
                                padding: const EdgeInsets.symmetric(vertical: 6),
                                child: Row(
                                  children: [
                                    SizedBox(
                                      width: 80,
                                      child: Text(e.key, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                                    ),
                                    Expanded(
                                      child: LinearProgressIndicator(
                                        value: pPower / 100.0,
                                        backgroundColor: AppTheme.surfaceBg,
                                        valueColor: const AlwaysStoppedAnimation(AppTheme.predatorGreen),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Text("${pPower.toStringAsFixed(0)}% Power", style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                                  ],
                                ),
                              );
                            }),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),

                // Liquidity Tier Breakdown
                Expanded(
                  flex: 3,
                  child: Card(
                    color: AppTheme.cardBg,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("PERFORMANCE BY LIQUIDITY BRACKET", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.accentCyan)),
                          const Divider(height: 20),
                          if (byTier.isEmpty)
                            const Text("No liquidity tier data available", style: TextStyle(color: AppTheme.textMuted, fontSize: 12))
                          else
                            ...byTier.entries.map((e) {
                              final data = e.value as Map<String, dynamic>;
                              final acc = ((data["accuracy"] ?? 0.0) as num).toDouble() * 100.0;
                              final ret = ((data["avg_return_pct"] ?? 0.0) as num).toDouble();
                              return Padding(
                                padding: const EdgeInsets.symmetric(vertical: 6),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(e.key, style: const TextStyle(fontSize: 12)),
                                    Row(
                                      children: [
                                        Text("${acc.toStringAsFixed(1)}% Acc", style: const TextStyle(fontSize: 11, color: AppTheme.predatorGreen)),
                                        const SizedBox(width: 12),
                                        Text("${ret >= 0 ? '+' : ''}${ret.toStringAsFixed(2)}% Ret", style: TextStyle(fontSize: 11, color: ret >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed)),
                                      ],
                                    ),
                                  ],
                                ),
                              );
                            }),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Versioned Strategy Benchmarks
            Card(
              color: AppTheme.cardBg,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text("STRATEGY VERSION BENCHMARKS (TEMPORAL VALIDATION)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.accentCyan)),
                    const SizedBox(height: 8),
                    const Text("Strategies must be strictly tested on historical validation splits before promotion to active paper trading.", style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                    const Divider(height: 20),
                    if (byStrategy.isEmpty)
                      const Text("No versioned benchmark records found", style: TextStyle(color: AppTheme.textMuted, fontSize: 12))
                    else
                      Table(
                        columnWidths: const {
                          0: FlexColumnWidth(2),
                          1: FlexColumnWidth(1),
                          2: FlexColumnWidth(1),
                          3: FlexColumnWidth(1),
                          4: FlexColumnWidth(2),
                        },
                        children: [
                          const TableRow(
                            decoration: BoxDecoration(border: Border(bottom: BorderSide(color: AppTheme.surfaceBg))),
                            children: [
                              Padding(padding: EdgeInsets.all(8), child: Text("Strategy Version", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Sample", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Accuracy", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Avg Return", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Status", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                            ],
                          ),
                          ...byStrategy.entries.map((e) {
                            final data = e.value as Map<String, dynamic>;
                            final count = data["count"] ?? 0;
                            final acc = ((data["accuracy"] ?? 0.0) as num).toDouble() * 100.0;
                            final ret = ((data["avg_return_pct"] ?? 0.0) as num).toDouble();
                            return TableRow(
                              children: [
                                Padding(padding: const EdgeInsets.all(8), child: Text(e.key, style: const TextStyle(fontSize: 11, color: AppTheme.predatorGreen))),
                                Padding(padding: const EdgeInsets.all(8), child: Text("$count", style: const TextStyle(fontSize: 11))),
                                Padding(padding: const EdgeInsets.all(8), child: Text("${acc.toStringAsFixed(1)}%", style: const TextStyle(fontSize: 11))),
                                Padding(padding: const EdgeInsets.all(8), child: Text("${ret.toStringAsFixed(2)}%", style: TextStyle(fontSize: 11, color: ret >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed))),
                                const Padding(
                                  padding: EdgeInsets.all(8),
                                  child: Text("ACTIVE BASELINE", style: TextStyle(fontSize: 10, color: AppTheme.predatorGreen, fontWeight: FontWeight.bold)),
                                ),
                              ],
                            );
                          }),
                        ],
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metricCard(String title, String value, IconData icon, Color color) {
    return Card(
      color: AppTheme.cardBg,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(child: Text(title, style: const TextStyle(fontSize: 10, color: AppTheme.textMuted), overflow: TextOverflow.ellipsis)),
                Icon(icon, size: 14, color: color),
              ],
            ),
            const SizedBox(height: 6),
            Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
          ],
        ),
      ),
    );
  }
}
