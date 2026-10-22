import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class PaperPortfolioView extends ConsumerWidget {
  const PaperPortfolioView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final portfolio = ref.watch(portfolioProvider);
    final positions = ref.watch(positionsProvider);
    final openPos = positions.where((p) => p.isOpen).toList();

    final totalEquity = portfolio?.totalEquityUsd ?? 10000.0;
    final cashBalance = portfolio?.cashBalanceUsd ?? 10000.0;
    final realizedPnl = portfolio?.totalRealizedPnlUsd ?? 0.0;
    final unrealizedPnl = portfolio?.totalUnrealizedPnlUsd ?? 0.0;
    final maxDrawdown = (portfolio?.maxDrawdownPct ?? 0.0) * 100.0;
    final totalFees = portfolio?.totalFeesPaidUsd ?? 0.0;

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 10,
              children: [
                const Text(
                  "PAPER PORTFOLIO — DETERMINISTIC SIMULATOR",
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.solanaCyan,
                    letterSpacing: 1.1,
                  ),
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.cardBg,
                    foregroundColor: AppTheme.warningOrange,
                  ),
                  onPressed: () => ref.read(terminalControllerProvider).resetPortfolio(),
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text("Reset Balance"),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Primary Metrics Grid
            LayoutBuilder(
              builder: (context, constraints) {
                final cols = constraints.maxWidth > 600 ? 3 : 2;
                return GridView.count(
                  crossAxisCount: cols,
                  crossAxisSpacing: 10,
                  mainAxisSpacing: 10,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  childAspectRatio: cols == 3 ? 2.2 : 2.0,
                  children: [
                    _buildMetricCard("TOTAL EQUITY", "\$${totalEquity.toStringAsFixed(2)}", AppTheme.predatorGreen),
                    _buildMetricCard("CASH BALANCE", "\$${cashBalance.toStringAsFixed(2)}", AppTheme.solanaCyan),
                    _buildMetricCard("REALIZED PNL", "\$${realizedPnl.toStringAsFixed(2)}", realizedPnl >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed),
                    _buildMetricCard("UNREALIZED PNL", "\$${unrealizedPnl.toStringAsFixed(2)}", unrealizedPnl >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed),
                    _buildMetricCard("MAX DRAWDOWN", "${maxDrawdown.toStringAsFixed(2)}%", maxDrawdown > 10.0 ? AppTheme.dangerRed : AppTheme.textBright),
                    _buildMetricCard("FEES & SLIPPAGE", "\$${totalFees.toStringAsFixed(2)}", AppTheme.textMuted),
                  ],
                );
              },
            ),
            const SizedBox(height: 24),
            const Text(
              "ACTIVE PAPER POSITIONS",
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.textBright),
            ),
            const SizedBox(height: 12),
            openPos.isEmpty
                ? Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceBg,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppTheme.borderCol),
                    ),
                    child: const Center(
                      child: Text("No open simulated positions. Awaiting agent approvals.", style: TextStyle(color: AppTheme.textMuted)),
                    ),
                  )
                : ListView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: openPos.length,
                    itemBuilder: (context, idx) {
                      final p = openPos[idx];
                      return Card(
                        color: AppTheme.surfaceBg,
                        margin: const EdgeInsets.only(bottom: 8),
                        shape: RoundedRectangleBorder(
                          side: const BorderSide(color: AppTheme.borderCol),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text("${p.tokenSymbol} (${p.tokenMint.substring(0, 8)}...)", style: const TextStyle(fontWeight: FontWeight.bold)),
                                  Text("Qty: ${p.qty.toStringAsFixed(2)} @ \$${p.averageEntryPriceUsd.toStringAsFixed(6)}", style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                                ],
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text("\$${p.currentValueUsd.toStringAsFixed(2)}", style: const TextStyle(fontWeight: FontWeight.bold)),
                                  Text(
                                    "${p.unrealizedPnlPct >= 0 ? '+' : ''}${p.unrealizedPnlPct.toStringAsFixed(2)}% (\$${p.unrealizedPnlUsd.toStringAsFixed(2)})",
                                    style: TextStyle(
                                      color: p.unrealizedPnlUsd >= 0 ? AppTheme.predatorGreen : AppTheme.dangerRed,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(String title, String val, Color valColor) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(title, style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(val, style: TextStyle(color: valColor, fontSize: 16, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
