import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class MarketOverviewView extends ConsumerWidget {
  const MarketOverviewView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = ref.watch(tokensProvider);
    final events = ref.watch(eventsProvider);

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text(
                    "MARKET OVERVIEW — DISCOVERED PAIRS",
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.solanaCyan,
                      letterSpacing: 1.1,
                    ),
                  ),
                ),
                Text(
                  "Total: ${tokens.length}",
                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: tokens.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.radar, size: 48, color: AppTheme.textMuted),
                          const SizedBox(height: 12),
                          const Text(
                            "Awaiting live Solana market pairs...",
                            style: TextStyle(color: AppTheme.textMuted),
                          ),
                          const SizedBox(height: 12),
                          ElevatedButton.icon(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.surfaceBg,
                              foregroundColor: AppTheme.predatorGreen,
                            ),
                            onPressed: () => ref.read(terminalControllerProvider).triggerReplay(),
                            icon: const Icon(Icons.play_arrow),
                            label: const Text("Inject Replay Market Events"),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      itemCount: tokens.length,
                      itemBuilder: (context, idx) {
                        final tok = tokens[idx];
                        // Find latest event matching this token
                        final latestEv = events.where((e) => e.tokenMint == tok.mint).firstOrNull;

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
                              children: [
                                CircleAvatar(
                                  backgroundColor: AppTheme.cardBg,
                                  child: Text(
                                    tok.symbol?.substring(0, 1) ?? "T",
                                    style: const TextStyle(color: AppTheme.predatorGreen, fontWeight: FontWeight.bold),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text(
                                            tok.symbol ?? "UNKNOWN",
                                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                          ),
                                          const SizedBox(width: 8),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(
                                              color: AppTheme.cardBg,
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              tok.currentLifecycleState,
                                              style: TextStyle(
                                                fontSize: 10,
                                                color: tok.currentLifecycleState == "PAPER_CANDIDATE"
                                                    ? AppTheme.predatorGreen
                                                    : tok.currentLifecycleState == "REJECTED"
                                                        ? AppTheme.dangerRed
                                                        : AppTheme.solanaCyan,
                                                fontWeight: FontWeight.bold,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        tok.mint,
                                        style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                                      ),
                                    ],
                                  ),
                                ),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Text(
                                      latestEv?.priceUsd != null ? "\$${latestEv!.priceUsd!.toStringAsFixed(6)}" : "PRICE UNVERIFIED",
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: latestEv?.priceUsd != null ? AppTheme.textBright : AppTheme.warningOrange,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      latestEv?.liquidityUsd != null
                                          ? "Liq: \$${latestEv!.liquidityUsd!.toStringAsFixed(0)}"
                                          : "Liq: N/A",
                                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 11),
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
}
