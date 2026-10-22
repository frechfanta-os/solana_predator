import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class ExitAnalysisView extends ConsumerWidget {
  const ExitAnalysisView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final positions = ref.watch(positionsProvider);
    final openPositions = positions.where((p) => p.isOpen).toList();

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "EXIT MONITOR — LIQUIDATION TRIGGERS",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              "Continuous evaluation: Stop Loss (-15%), Take Profit (+50%), Trailing Pullback (-20%), Liquidity Collapse, Whale Sells",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: openPositions.isEmpty
                  ? const Center(
                      child: Text("No open positions currently under exit monitoring.", style: TextStyle(color: AppTheme.textMuted)),
                    )
                  : ListView.builder(
                      itemCount: openPositions.length,
                      itemBuilder: (context, idx) {
                        final p = openPositions[idx];

                        return Card(
                          color: AppTheme.surfaceBg,
                          margin: const EdgeInsets.only(bottom: 12),
                          shape: RoundedRectangleBorder(
                            side: const BorderSide(color: AppTheme.borderCol),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      "${p.tokenSymbol} (${p.tokenMint.substring(0, 8)}...)",
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                    ),
                                    Text(
                                      "PnL: ${p.unrealizedPnlPct.toStringAsFixed(2)}%",
                                      style: TextStyle(
                                        color: p.unrealizedPnlPct >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                // Stop Loss & Take Profit progress bars
                                _buildTriggerBar("Stop Loss (-15%)", p.unrealizedPnlPct, -15.0, AppTheme.dangerRed),
                                const SizedBox(height: 8),
                                _buildTriggerBar("Take Profit (+50%)", p.unrealizedPnlPct, 50.0, AppTheme.predatorGreen),
                                const Divider(height: 20),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text("Peak Price: \$${p.currentPriceUsd.toStringAsFixed(6)}", style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                                    Text("Est. Exit Cost: ~55 bps", style: const TextStyle(color: AppTheme.warningOrange, fontSize: 11)),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTriggerBar(String label, double currentPct, double targetPct, Color col) {
    double progress = 0.0;
    if (targetPct > 0) {
      progress = (currentPct / targetPct).clamp(0.0, 1.0);
    } else {
      progress = (currentPct / targetPct).clamp(0.0, 1.0);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
            Text("${currentPct.toStringAsFixed(1)}% / ${targetPct.toStringAsFixed(0)}%", style: TextStyle(color: col, fontSize: 11, fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: progress,
          backgroundColor: AppTheme.cardBg,
          valueColor: AlwaysStoppedAnimation<Color>(col),
          minHeight: 4,
        ),
      ],
    );
  }
}
