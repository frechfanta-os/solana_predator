import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class WhaleActivityView extends ConsumerWidget {
  const WhaleActivityView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activities = ref.watch(whaleActivitiesProvider);

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "WHALE INTELLIGENCE — ON-CHAIN FLOWS",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              "Classified activities: SWAP, TRANSFER, DEPOSIT_WITHDRAW, UNKNOWN_AMBIGUOUS",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: activities.isEmpty
                  ? const Center(
                      child: Text("No observable whale transactions detected yet.", style: TextStyle(color: AppTheme.textMuted)),
                    )
                  : ListView.builder(
                      itemCount: activities.length,
                      itemBuilder: (context, idx) {
                        final act = activities[idx];
                        final t = DateTime.fromMillisecondsSinceEpoch((act.timestamp * 1000).toInt());

                        Color actCol;
                        if (act.activityType == "SWAP") {
                          actCol = AppTheme.predatorGreen;
                        } else if (act.activityType == "TRANSFER") {
                          actCol = AppTheme.solanaCyan;
                        } else {
                          actCol = AppTheme.warningOrange;
                        }

                        return Card(
                          color: AppTheme.surfaceBg,
                          margin: const EdgeInsets.only(bottom: 8),
                          shape: RoundedRectangleBorder(
                            side: const BorderSide(color: AppTheme.borderCol),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: ListTile(
                            leading: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: actCol.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Icon(
                                act.activityType == "SWAP" ? Icons.swap_horiz : Icons.account_balance_wallet,
                                color: actCol,
                                size: 20,
                              ),
                            ),
                            title: Row(
                              children: [
                                Text(
                                  act.activityType,
                                  style: TextStyle(color: actCol, fontWeight: FontWeight.bold, fontSize: 13),
                                ),
                                const SizedBox(width: 8),
                                if (act.amountUsd != null)
                                  Text(
                                    "\$${act.amountUsd!.toStringAsFixed(2)}",
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                  ),
                              ],
                            ),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const SizedBox(height: 4),
                                Text(
                                  "Wallet: ${act.walletAddress}",
                                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                                ),
                                Text(
                                  "Sig: ${act.signature.substring(0, 16)}...",
                                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                                ),
                              ],
                            ),
                            trailing: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  "${t.hour}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')}",
                                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 11),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  "Conf: ${(act.confidence * 100).toInt()}%",
                                  style: const TextStyle(color: AppTheme.solanaCyan, fontSize: 10),
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
