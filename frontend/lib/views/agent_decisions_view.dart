import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class AgentDecisionsView extends ConsumerWidget {
  const AgentDecisionsView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final decisions = ref.watch(agentDecisionsProvider);

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "MULTI-AGENT ENGINE — DECISION TIMELINE",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              "Agents: CHIEF, SCAN, WHALE, VET, QUANT, SKEPTIC, SIZE, RISK, AUDIT",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: decisions.isEmpty
                  ? const Center(
                      child: Text("No multi-agent decisions logged yet.", style: TextStyle(color: AppTheme.textMuted)),
                    )
                  : ListView.builder(
                      itemCount: decisions.length,
                      itemBuilder: (context, idx) {
                        final dec = decisions[idx];
                        final t = DateTime.fromMillisecondsSinceEpoch((dec.timestamp * 1000).toInt());

                        Color decColor;
                        if (dec.decision == "BUY_CANDIDATE") {
                          decColor = AppTheme.predatorGreen;
                        } else if (dec.decision == "VETO") {
                          decColor = AppTheme.dangerRed;
                        } else if (dec.decision == "EXIT") {
                          decColor = AppTheme.warningOrange;
                        } else {
                          decColor = AppTheme.solanaCyan;
                        }

                        return Card(
                          color: AppTheme.surfaceBg,
                          margin: const EdgeInsets.only(bottom: 10),
                          shape: RoundedRectangleBorder(
                            side: const BorderSide(color: AppTheme.borderCol),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Row(
                                      children: [
                                        Text(
                                          dec.agentName,
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.solanaCyan),
                                        ),
                                        const SizedBox(width: 8),
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: decColor.withValues(alpha: 0.15),
                                            border: Border.all(color: decColor),
                                            borderRadius: BorderRadius.circular(4),
                                          ),
                                          child: Text(
                                            dec.decision,
                                            style: TextStyle(color: decColor, fontSize: 10, fontWeight: FontWeight.bold),
                                          ),
                                        ),
                                      ],
                                    ),
                                    Text(
                                      "${dec.latencyMs.toStringAsFixed(1)} ms",
                                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 11),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  dec.reasonCodes.join(" • "),
                                  style: const TextStyle(fontSize: 12),
                                ),
                                const SizedBox(height: 6),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      "Mint: ${dec.tokenMint.substring(0, 16)}...",
                                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                                    ),
                                    Text(
                                      "${t.hour}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')}",
                                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
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
