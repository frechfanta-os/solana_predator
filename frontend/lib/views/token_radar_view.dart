import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class TokenRadarView extends ConsumerWidget {
  const TokenRadarView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = ref.watch(tokensProvider);

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "NEW TOKEN RADAR — LIFECYCLE TRACKER",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              "Lifecycle: DISCOVERED → OBSERVED → ANALYZED → REJECTED / PAPER_CANDIDATE",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: tokens.isEmpty
                  ? const Center(
                      child: Text("No tokens registered in radar yet.", style: TextStyle(color: AppTheme.textMuted)),
                    )
                  : ListView.builder(
                      itemCount: tokens.length,
                      itemBuilder: (context, idx) {
                        final tok = tokens[idx];
                        final firstSeen = DateTime.fromMillisecondsSinceEpoch((tok.firstObservedTimestamp * 1000).toInt());
                        final poolCreated = tok.poolCreatedTimestamp != null
                            ? DateTime.fromMillisecondsSinceEpoch((tok.poolCreatedTimestamp! * 1000).toInt())
                            : null;

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
                                      "${tok.name ?? 'Unknown'} (${tok.symbol ?? 'TOKEN'})",
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                    ),
                                    _buildStateBadge(tok.currentLifecycleState),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  "Mint: ${tok.mint}",
                                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 11, fontFamily: "monospace"),
                                ),
                                const Divider(height: 18),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const Text("First Observed", style: TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                                        Text("${firstSeen.hour}:${firstSeen.minute.toString().padLeft(2, '0')}:${firstSeen.second.toString().padLeft(2, '0')}", style: const TextStyle(fontSize: 12)),
                                      ],
                                    ),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const Text("Pool Creation", style: TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                                        Text(
                                          poolCreated != null
                                              ? "${poolCreated.hour}:${poolCreated.minute.toString().padLeft(2, '0')}:${poolCreated.second.toString().padLeft(2, '0')}"
                                              : "N/A",
                                          style: const TextStyle(fontSize: 12),
                                        ),
                                      ],
                                    ),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: [
                                        const Text("Initial Liquidity", style: TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                                        Text(
                                          tok.initialLiquidityUsd != null ? "\$${tok.initialLiquidityUsd!.toStringAsFixed(0)}" : "Unknown",
                                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                        ),
                                      ],
                                    ),
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

  Widget _buildStateBadge(String state) {
    Color col;
    if (state == "PAPER_CANDIDATE") {
      col = AppTheme.predatorGreen;
    } else if (state == "REJECTED") {
      col = AppTheme.dangerRed;
    } else if (state == "ANALYZED") {
      col = AppTheme.solanaCyan;
    } else {
      col = AppTheme.warningOrange;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: col.withValues(alpha: 0.15),
        border: Border.all(color: col),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        state,
        style: TextStyle(color: col, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }
}
