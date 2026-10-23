import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

class MarketOverviewView extends ConsumerStatefulWidget {
  const MarketOverviewView({super.key});

  @override
  ConsumerState<MarketOverviewView> createState() => _MarketOverviewViewState();
}

class _MarketOverviewViewState extends ConsumerState<MarketOverviewView> {
  String _searchQuery = "";
  final TextEditingController _watchController = TextEditingController();

  @override
  void dispose() {
    _watchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = ref.watch(tokensProvider);
    final events = ref.watch(eventsProvider);
    final watchlist = ref.watch(watchlistProvider).where((w) => w.itemType == "TOKEN").toList();
    final tasks = ref.watch(deskTasksProvider).where((t) => t.deskId == "DESK_MARKET").toList();
    final reports = ref.watch(deskReportsProvider).where((r) => r.deskId == "DESK_MARKET").toList();

    final filteredTokens = tokens.where((t) {
      if (_searchQuery.isEmpty) return true;
      final q = _searchQuery.toLowerCase();
      return (t.symbol?.toLowerCase().contains(q) ?? false) || t.mint.toLowerCase().contains(q);
    }).toList();

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const DeskWorkspaceHeader(deskId: "DESK_MARKET"),
            const SizedBox(height: 12),

            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text(
                    "MARKET OVERVIEW — DISCOVERED PAIRS",
                    style: TextStyle(
                      fontSize: 14,
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
            const SizedBox(height: 8),

            // Search Filter & Watchlist Adder
            Row(
              children: [
                Expanded(
                  child: TextField(
                    onChanged: (v) => setState(() => _searchQuery = v.trim()),
                    style: const TextStyle(fontSize: 12),
                    decoration: const InputDecoration(
                      isDense: true,
                      prefixIcon: Icon(Icons.search, size: 16),
                      hintText: "Filter pairs by symbol or base58 mint...",
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.surfaceBg,
                    foregroundColor: AppTheme.predatorGreen,
                  ),
                  onPressed: () => ref.read(terminalControllerProvider).triggerReplay(),
                  icon: const Icon(Icons.play_arrow, size: 16),
                  label: const Text("Inject Replay Market Events", style: TextStyle(fontSize: 11)),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Token Watchlist Section
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppTheme.borderCol),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "TOKEN WATCHLIST (DESK 1 MONITORED MINTS)",
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
                  ),
                  const SizedBox(height: 6),
                  if (watchlist.isEmpty)
                    const Text("No watched tokens configured.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
                  else
                    Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      children: watchlist.map((w) {
                        return Chip(
                          backgroundColor: AppTheme.cardBg,
                          label: Text(
                            "${w.label ?? 'TOKEN'} (${w.identifier.substring(0, 6)}...)",
                            style: const TextStyle(fontSize: 10, fontFamily: "monospace"),
                          ),
                          onDeleted: () => ref.read(terminalControllerProvider).removeWatchlistItem(w.identifier),
                        );
                      }).toList(),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Live Discovered Pairs List
            if (filteredTokens.isEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceBg,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppTheme.borderCol),
                ),
                child: const Center(
                  child: Text(
                    "Awaiting live Solana market pairs...",
                    style: TextStyle(color: AppTheme.textMuted),
                  ),
                ),
              )
            else
              ...filteredTokens.map((tok) {
                final latestEv = events.where((e) => e.tokenMint == tok.mint).firstOrNull;
                final isStale = (latestEv?.freshnessSeconds ?? 0.0) > 30.0 || latestEv?.quality == "STALE";

                return Card(
                  color: AppTheme.surfaceBg,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    side: BorderSide(color: isStale ? AppTheme.warningOrange : AppTheme.borderCol),
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
                              Wrap(
                                spacing: 8,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Text(
                                    tok.symbol ?? "UNKNOWN",
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                  ),
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
                                  if (latestEv != null)
                                    Text(
                                      "Source: ${latestEv.source} (${latestEv.freshnessSeconds.toStringAsFixed(1)}s)",
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: isStale ? AppTheme.warningOrange : AppTheme.textMuted,
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
                              latestEv?.priceUsd != null
                                  ? "\$${latestEv!.priceUsd!.toStringAsFixed(6)}"
                                  : "PRICE MISSING (UNVERIFIED)",
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: latestEv?.priceUsd != null ? AppTheme.textBright : AppTheme.warningOrange,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              latestEv?.liquidityUsd != null
                                  ? "Liq: \$${latestEv!.liquidityUsd!.toStringAsFixed(0)} • Vol: ${latestEv.volume24hUsd != null ? '\$${latestEv.volume24hUsd!.toStringAsFixed(0)}' : 'MISSING'}"
                                  : "Liq: MISSING",
                              style: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              }),

            const SizedBox(height: 16),
            const Text(
              "DESK 1 STRUCTURED MARKET REPORTS (SCAN)",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (reports.isEmpty)
              const Text("No market intelligence reports generated yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
            else
              ...reports.take(6).map((r) => StructuredReportCard(report: r)),

            const SizedBox(height: 14),
            const Text(
              "DESK 1 TASK EXECUTION HISTORY",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            DeskTaskExecutionList(tasks: tasks),
          ],
        ),
      ),
    );
  }
}
