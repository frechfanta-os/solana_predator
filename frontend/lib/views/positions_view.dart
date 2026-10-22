import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class PositionsView extends ConsumerStatefulWidget {
  const PositionsView({super.key});

  @override
  ConsumerState<PositionsView> createState() => _PositionsViewState();
}

class _PositionsViewState extends ConsumerState<PositionsView> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final positions = ref.watch(positionsProvider);
    final openPositions = positions.where((p) => p.isOpen).toList();
    final closedPositions = positions.where((p) => !p.isOpen).toList();

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(48),
        child: Container(
          color: AppTheme.surfaceBg,
          child: TabBar(
            controller: _tabController,
            indicatorColor: AppTheme.predatorGreen,
            tabs: [
              Tab(text: "OPEN POSITIONS (${openPositions.length})"),
              Tab(text: "CLOSED POSITIONS (${closedPositions.length})"),
            ],
          ),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildPositionsList(openPositions, true),
          _buildPositionsList(closedPositions, false),
        ],
      ),
    );
  }

  Widget _buildPositionsList(List<dynamic> list, bool isOpenTab) {
    if (list.isEmpty) {
      return Center(
        child: Text(
          isOpenTab ? "No active positions." : "No closed positions recorded.",
          style: const TextStyle(color: AppTheme.textMuted),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: list.length,
      itemBuilder: (context, idx) {
        final p = list[idx];
        final pnl = isOpenTab ? p.unrealizedPnlUsd : p.realizedPnlUsd;
        final pnlPct = isOpenTab ? p.unrealizedPnlPct : 0.0;
        final isProfit = pnl >= 0;

        return Card(
          color: AppTheme.surfaceBg,
          margin: const EdgeInsets.only(bottom: 10),
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
                    Row(
                      children: [
                        Text(
                          p.tokenSymbol,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                        ),
                        const SizedBox(width: 8),
                        if (isOpenTab && p.isStalePrice)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppTheme.warningOrange.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: AppTheme.warningOrange),
                            ),
                            child: const Text("STALE PRICE", style: TextStyle(color: AppTheme.warningOrange, fontSize: 9, fontWeight: FontWeight.bold)),
                          ),
                      ],
                    ),
                    Text(
                      "${isProfit ? '+' : ''}\$${pnl.toStringAsFixed(2)} ${isOpenTab ? '(${pnlPct.toStringAsFixed(2)}%)' : ''}",
                      style: TextStyle(
                        color: isProfit ? AppTheme.predatorGreen : AppTheme.dangerRed,
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  "Mint: ${p.tokenMint}",
                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                ),
                const Divider(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text("Entry Price", style: TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                        Text("\$${p.averageEntryPriceUsd.toStringAsFixed(6)}", style: const TextStyle(fontSize: 12)),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(isOpenTab ? "Mark Price" : "Exit Price", style: const TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                        Text("\$${p.currentPriceUsd.toStringAsFixed(6)}", style: const TextStyle(fontSize: 12)),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        const Text("Invested Capital", style: TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                        Text("\$${p.investedCapitalUsd.toStringAsFixed(2)}", style: const TextStyle(fontSize: 12)),
                      ],
                    ),
                  ],
                ),
                if (!isOpenTab && p.exitReason != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    "Exit Reason: ${p.exitReason}",
                    style: const TextStyle(color: AppTheme.warningOrange, fontSize: 11, fontStyle: FontStyle.italic),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
