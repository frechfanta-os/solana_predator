import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

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
      ref.read(terminalControllerProvider).fetchStrategyBenchmarks();
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
    final tasks = ref.watch(deskTasksProvider).where((t) => t.deskId == "DESK_QUANT").toList();
    final reports = ref.watch(deskReportsProvider).where((r) => r.deskId == "DESK_QUANT").toList();

    final totalDecisions = metrics["total_decisions_evaluated"] ?? 0;
    final accuracyRate = ((metrics["correct_decisions_rate"] ?? 0.0) as num).toDouble() * 100.0;
    final falsePositiveRate = ((metrics["false_positive_rate"] ?? 0.0) as num).toDouble() * 100.0;
    final simulatedReturn = ((metrics["simulated_net_return_pct"] ?? 0.0) as num).toDouble();
    final maxDrawdown = ((metrics["max_simulated_drawdown_pct"] ?? 0.0) as num).toDouble();
    final maePrice = ((metrics["mean_absolute_error_price"] ?? 0.0) as num).toDouble();

    final byAgent = (metrics["results_by_agent"] as Map<String, dynamic>?) ?? {};
    final byStrategy = (metrics["results_by_strategy"] as Map<String, dynamic>?) ?? {};

    return Scaffold(
      backgroundColor: AppTheme.scaffoldBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const DeskWorkspaceHeader(deskId: "DESK_QUANT"),
            const SizedBox(height: 12),

            // Header with action (Preserves exact text tested in widget_test.dart)
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "MEASURABLE LEARNING ENGINE",
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.predatorGreen),
                      ),
                      SizedBox(height: 4),
                      Text(
                        "Chronological TRAIN (60%) / VALIDATION (20%) / TEST (20%) splits without lookahead bias. Includes 25 bps fee + slippage.",
                        style: TextStyle(fontSize: 11, color: AppTheme.textMuted),
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
            const SizedBox(height: 10),

            // Mandatory Research Disclaimer
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: AppTheme.borderCol),
              ),
              child: const Text(
                "QUANT RESEARCH NOTICE: Historical backtests and simulated returns incorporate transaction-cost assumptions and uncertainty bounds; they are never proof of future profitability.",
                style: TextStyle(fontSize: 10, color: AppTheme.warningOrange),
              ),
            ),
            const SizedBox(height: 14),

            // Metrics Cards Layout
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
            const SizedBox(height: 16),

            // Agent Attribution & Strategy Benchmarks
            Card(
              color: AppTheme.cardBg,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text("AGENT PERFORMANCE ATTRIBUTION & STRATEGY BENCHMARKS", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppTheme.accentCyan)),
                    const Divider(height: 16),
                    if (byAgent.isEmpty && byStrategy.isEmpty)
                      const Text("No evaluated agent outcomes yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
                    else
                      ...byAgent.entries.map((e) {
                        final data = e.value as Map<String, dynamic>;
                        final pPower = ((data["predictive_power"] ?? data["accuracy_rate_pct"] ?? 75.0) as num).toDouble();
                        final displayPct = pPower <= 1.0 ? pPower * 100.0 : pPower;
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Row(
                            children: [
                              SizedBox(width: 80, child: Text(e.key, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Expanded(
                                child: LinearProgressIndicator(
                                  value: (displayPct / 100.0).clamp(0.0, 1.0),
                                  backgroundColor: AppTheme.surfaceBg,
                                  valueColor: const AlwaysStoppedAnimation(AppTheme.predatorGreen),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Text("${displayPct.toStringAsFixed(1)}%", style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                            ],
                          ),
                        );
                      }),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            const Text(
              "DESK 4 QUANT RESEARCH REPORTS (QUANT)",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (reports.isEmpty)
              const Text("No quant research reports generated yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
            else
              ...reports.take(6).map((r) => StructuredReportCard(report: r)),

            const SizedBox(height: 14),
            const Text(
              "DESK 4 TASK EXECUTION HISTORY",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            DeskTaskExecutionList(tasks: tasks),
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
