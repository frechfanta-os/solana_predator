import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

class AgentDecisionsView extends ConsumerWidget {
  const AgentDecisionsView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agents = ref.watch(agentsStatusProvider);
    final tasks = ref.watch(deskTasksProvider);
    final decisions = ref.watch(agentDecisionsProvider);

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "AGENT ACTIVITY & EXECUTION TELEMETRY",
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              "Real-time status of all 9 agents (SCAN, WHALE, VET, QUANT, SKEPTIC, SIZE, RISK, CHIEF, AUDIT) across the 6 specialized desks.",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
            ),
            const SizedBox(height: 12),

            // 9 Agent Status Cards
            if (agents.isNotEmpty)
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: agents.map((ag) {
                  final col = statusColorForState(ag.status);
                  return Container(
                    width: 210,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceBg,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppTheme.borderCol),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(ag.agentId, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppTheme.solanaCyan)),
                            Text(ag.status, style: TextStyle(color: col, fontSize: 10, fontWeight: FontWeight.bold)),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text("Desk: ${ag.deskId}", style: const TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                        Text(
                          "Completed: ${ag.completedTasks} | Failed: ${ag.failedTasks}",
                          style: const TextStyle(color: AppTheme.textBright, fontSize: 10),
                        ),
                        Text(
                          "Latency: ${ag.lastDurationMs.toStringAsFixed(1)} ms • Last: ${ag.lastDecision ?? 'N/A'}",
                          style: const TextStyle(color: AppTheme.predatorGreen, fontSize: 9, fontFamily: "monospace"),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            const SizedBox(height: 16),

            const Text(
              "RECENT MULTI-AGENT TASK EXECUTIONS",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            DeskTaskExecutionList(tasks: tasks),
            const SizedBox(height: 16),

            const Text(
              "MULTI-AGENT ENGINE — DECISION TIMELINE",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (decisions.isEmpty)
              const Text("No multi-agent decisions logged yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
            else
              ...decisions.take(15).map((dec) {
                final decColor = dec.decision == "BUY_CANDIDATE"
                    ? AppTheme.predatorGreen
                    : dec.decision == "VETO"
                        ? AppTheme.dangerRed
                        : AppTheme.solanaCyan;
                return Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceBg,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppTheme.borderCol),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          "[${dec.agentName}] ${dec.decision} — ${dec.reasonCodes.join(' • ')}",
                          style: TextStyle(color: decColor, fontSize: 11, fontWeight: FontWeight.w500),
                        ),
                      ),
                      Text(
                        "${dec.latencyMs.toStringAsFixed(1)} ms",
                        style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                      ),
                    ],
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}
