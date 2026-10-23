import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

class WhaleActivityView extends ConsumerWidget {
  const WhaleActivityView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activities = ref.watch(whaleActivitiesProvider);
    final walletWatchlist = ref.watch(watchlistProvider).where((w) => w.itemType == "WALLET").toList();
    final tasks = ref.watch(deskTasksProvider).where((t) => t.deskId == "DESK_WHALE").toList();
    final reports = ref.watch(deskReportsProvider).where((r) => r.deskId == "DESK_WHALE").toList();

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const DeskWorkspaceHeader(deskId: "DESK_WHALE"),
            const SizedBox(height: 12),

            const Text(
              "WHALE INTELLIGENCE — ON-CHAIN FLOWS",
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              "Classified activities: SWAP_INFLOW, SWAP_OUTFLOW, SPL_TRANSFER_ONLY, FAILED. Distinguishes observed transactions from inferred convergence.",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
            ),
            const SizedBox(height: 12),

            // Public Wallet Watchlist
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
                    "TRACKED PUBLIC WALLET ADDRESSES (READ-ONLY ON-CHAIN)",
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
                  ),
                  const SizedBox(height: 6),
                  if (walletWatchlist.isEmpty)
                    const Text("No public wallets in watchlist.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
                  else
                    ...walletWatchlist.map((w) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 3),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                "${w.label ?? 'Public Wallet'}: ${w.identifier}",
                                style: const TextStyle(fontSize: 11, fontFamily: "monospace"),
                              ),
                              Text(
                                w.notes ?? "Observed only — unverified identity",
                                style: const TextStyle(fontSize: 10, color: AppTheme.textMuted),
                              ),
                            ],
                          ),
                        )),
                ],
              ),
            ),
            const SizedBox(height: 14),

            // Observed Whale Activity List
            if (activities.isEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceBg,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppTheme.borderCol),
                ),
                child: const Center(
                  child: Text("No observable whale transactions detected yet.", style: TextStyle(color: AppTheme.textMuted)),
                ),
              )
            else
              ...activities.map((act) {
                final t = DateTime.fromMillisecondsSinceEpoch((act.timestamp * 1000).toInt()).toLocal();
                final actCol = act.activityType.contains("INFLOW") || act.activityType == "SWAP"
                    ? AppTheme.predatorGreen
                    : act.activityType.contains("OUTFLOW")
                        ? AppTheme.dangerRed
                        : AppTheme.solanaCyan;

                return Card(
                  color: AppTheme.surfaceBg,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    side: const BorderSide(color: AppTheme.borderCol),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: ListTile(
                    leading: Icon(Icons.waves, color: actCol, size: 20),
                    title: Row(
                      children: [
                        Text(
                          act.activityType,
                          style: TextStyle(color: actCol, fontWeight: FontWeight.bold, fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          act.amountUsd != null ? "\$${act.amountUsd!.toStringAsFixed(2)}" : "USD UNVERIFIED",
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                        ),
                      ],
                    ),
                    subtitle: Text(
                      "Wallet: ${act.walletAddress} • Sig: ${act.signature.length > 14 ? act.signature.substring(0, 14) : act.signature}...",
                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                    ),
                    trailing: Text(
                      "${t.hour}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')} • Conf ${(act.confidence * 100).toInt()}%",
                      style: const TextStyle(color: AppTheme.solanaCyan, fontSize: 10, fontFamily: "monospace"),
                    ),
                  ),
                );
              }),

            const SizedBox(height: 16),
            const Text(
              "DESK 2 STRUCTURED WHALE REPORTS (WHALE)",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (reports.isEmpty)
              const Text("No whale intelligence reports generated yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
            else
              ...reports.take(6).map((r) => StructuredReportCard(report: r)),

            const SizedBox(height: 14),
            const Text(
              "DESK 2 TASK EXECUTION HISTORY",
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
