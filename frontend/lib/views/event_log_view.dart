import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class EventLogView extends ConsumerWidget {
  const EventLogView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
                const Text(
                  "NORMALIZED EVENT LOG — INGESTION STREAM",
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.solanaCyan,
                    letterSpacing: 1.1,
                  ),
                ),
                Text(
                  "Events: ${events.length}",
                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: events.isEmpty
                  ? const Center(
                      child: Text("No normalized events recorded in current session.", style: TextStyle(color: AppTheme.textMuted)),
                    )
                  : ListView.builder(
                      itemCount: events.length,
                      itemBuilder: (context, idx) {
                        final ev = events[idx];
                        final t = DateTime.fromMillisecondsSinceEpoch((ev.localReceiveTimestamp * 1000).toInt());

                        Color qCol;
                        if (ev.quality == "EXCELLENT") {
                          qCol = AppTheme.predatorGreen;
                        } else if (ev.quality == "DEGRADED" || ev.quality == "STALE") {
                          qCol = AppTheme.warningOrange;
                        } else {
                          qCol = AppTheme.solanaCyan;
                        }

                        return Card(
                          color: AppTheme.surfaceBg,
                          margin: const EdgeInsets.only(bottom: 6),
                          shape: RoundedRectangleBorder(
                            side: const BorderSide(color: AppTheme.borderCol),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            child: Row(
                              children: [
                                Text(
                                  "${t.hour}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')}",
                                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 11, fontFamily: "monospace"),
                                ),
                                const SizedBox(width: 10),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: AppTheme.cardBg,
                                    borderRadius: BorderRadius.circular(3),
                                  ),
                                  child: Text(
                                    ev.source,
                                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: qCol.withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(3),
                                  ),
                                  child: Text(
                                    ev.quality,
                                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: qCol),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    "${ev.tokenMint.substring(0, 12)}... | ${ev.priceUsd != null ? '\$${ev.priceUsd!.toStringAsFixed(6)}' : 'No Price'}",
                                    style: const TextStyle(fontSize: 11),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                Text(
                                  "Lag: ${ev.freshnessSeconds.toStringAsFixed(2)}s",
                                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
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
