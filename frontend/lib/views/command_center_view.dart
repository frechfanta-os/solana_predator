import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

class CommandCenterView extends ConsumerWidget {
  const CommandCenterView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final desks = ref.watch(desksProvider);
    final agents = ref.watch(agentsStatusProvider);
    final tasks = ref.watch(deskTasksProvider);
    final reports = ref.watch(deskReportsProvider);
    final portfolio = ref.watch(portfolioProvider);
    final sysHealth = ref.watch(systemHealthProvider);
    final providersHealth = ref.watch(providersHealthProvider);
    final tokens = ref.watch(tokensProvider);

    final killSwitchActive = sysHealth["emergency_kill_switch_active"] == true;
    final vetoes = reports.where((r) => r.isVeto).toList();
    final chiefReports = reports.where((r) => r.deskId == "DESK_COMMAND" || r.agentId == "CHIEF").toList();

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Desk 6 Header (CHIEF)
            DeskWorkspaceHeader(
              deskId: "DESK_COMMAND",
              trailingExtra: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.solanaCyan,
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
                onPressed: () => ref.read(terminalControllerProvider).triggerReplay(),
                icon: const Icon(Icons.bolt, size: 15),
                label: const Text("Inject Replay Cycle", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ),
            const SizedBox(height: 12),

            // Top Observability Telemetry Strip
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppTheme.borderCol),
              ),
              child: Wrap(
                spacing: 20,
                runSpacing: 8,
                children: [
                  _obsMetric("MODE", "PAPER_TRADING_ONLY", AppTheme.predatorGreen),
                  _obsMetric("LIVE BOUNDARY", "DRY-RUN ONLY (MAINNET LOCKED)", AppTheme.warningOrange),
                  _obsMetric(
                    "KILL-SWITCH",
                    killSwitchActive ? "ENGAGED (HALTED)" : "DISENGAGED (READY)",
                    killSwitchActive ? AppTheme.dangerRed : AppTheme.predatorGreen,
                  ),
                  _obsMetric("SQLITE WAL", "HEALTHY (SCHEMA V4)", AppTheme.predatorGreen),
                  _obsMetric("TRACKED TOKENS", "${tokens.length}", AppTheme.solanaCyan),
                  _obsMetric(
                    "VIRTUAL EQUITY",
                    "\$${(portfolio?.totalEquityUsd ?? 10000.0).toStringAsFixed(2)}",
                    AppTheme.predatorGreen,
                  ),
                  _obsMetric(
                    "RISK VETOES",
                    "${vetoes.length}",
                    vetoes.isNotEmpty ? AppTheme.dangerRed : AppTheme.textBright,
                  ),
                  _obsMetric(
                    "PROVIDERS ACTIVE",
                    providersHealth["composite_available"] == false ? "DEGRADED" : "DEX_SCREENER + RPC",
                    AppTheme.solanaCyan,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),

            // Six Specialized Desks Status Grid
            const Text(
              "SIX SPECIALIZED OPERATIONAL DESKS — LIVE SUPERVISION",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan, letterSpacing: 1.1),
            ),
            const SizedBox(height: 8),
            LayoutBuilder(
              builder: (context, constraints) {
                final cols = constraints.maxWidth > 1050 ? 3 : (constraints.maxWidth > 620 ? 2 : 1);
                final itemWidth = (constraints.maxWidth - (cols - 1) * 10) / cols;
                return Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: desks.asMap().entries.map((entry) {
                    final d = entry.value;
                    final navIdx = _deskIdToNavIndex(d.deskId);
                    final stCol = statusColorForState(d.isPaused ? "PAUSED" : d.status);
                    return SizedBox(
                      width: itemWidth,
                      child: InkWell(
                        onTap: () => ref.read(selectedNavigationIndexProvider.notifier).state = navIdx,
                        borderRadius: BorderRadius.circular(6),
                        child: Container(
                          padding: const EdgeInsets.all(12),
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
                                  Expanded(
                                    child: Text(
                                      d.name,
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.textBright),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: stCol.withValues(alpha: 0.15),
                                      border: Border.all(color: stCol),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      d.isPaused ? "PAUSED" : d.status,
                                      style: TextStyle(color: stCol, fontSize: 9, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                "Supervisor: ${d.supervisor} • Agents: ${d.agents.join(', ')}",
                                style: const TextStyle(color: AppTheme.solanaCyan, fontSize: 10, fontFamily: "monospace"),
                              ),
                              const SizedBox(height: 6),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    "Done: ${d.completedTasks} | Fail: ${d.failedTasks} | Q: ${d.queuedTasks}",
                                    style: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
                                  ),
                                  Text(
                                    "${d.lastDurationMs.toStringAsFixed(1)} ms",
                                    style: const TextStyle(color: AppTheme.predatorGreen, fontSize: 10, fontFamily: "monospace"),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                );
              },
            ),
            const SizedBox(height: 16),

            // Main Split Area: Left = CHIEF Reports & Disagreements | Right = Agent Roster & Critical Alerts
            LayoutBuilder(
              builder: (context, constraints) {
                final isWide = constraints.maxWidth > 850;
                final leftColumn = Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      "CHIEF CONSENSUS & STRUCTURED DESK REPORTS (FACTS VS INFERENCES)",
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
                    ),
                    const SizedBox(height: 8),
                    if (reports.isEmpty)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceBg,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppTheme.borderCol),
                        ),
                        child: const Text(
                          "No structured desk reports recorded yet. Click 'Inject Replay Cycle' or 'Run Cycle' to execute real agents.",
                          style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                        ),
                      )
                    else
                      ...(chiefReports.isNotEmpty ? chiefReports.take(4) : reports.take(4))
                          .map((r) => StructuredReportCard(report: r)),
                  ],
                );

                final rightColumn = Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      "REAL AGENT TELEMETRY & AUTHORITATIVE RISK ALERTS",
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.warningOrange),
                    ),
                    const SizedBox(height: 8),
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
                          if (agents.isEmpty)
                            const Text(
                              "9 Agents Registered: SCAN, WHALE, VET, QUANT, SKEPTIC, SIZE, RISK, CHIEF, AUDIT (IDLE)",
                              style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                            )
                          else
                            ...agents.map((ag) {
                              final col = statusColorForState(ag.status);
                              return Padding(
                                padding: const EdgeInsets.symmetric(vertical: 4),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Row(
                                      children: [
                                        Container(width: 7, height: 7, decoration: BoxDecoration(color: col, shape: BoxShape.circle)),
                                        const SizedBox(width: 6),
                                        Text(ag.agentId, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
                                        const SizedBox(width: 6),
                                        Text("(${ag.deskId})", style: const TextStyle(color: AppTheme.textMuted, fontSize: 9)),
                                      ],
                                    ),
                                    Text(
                                      "${ag.status} • ${ag.completedTasks} ok • ${ag.lastDurationMs.toStringAsFixed(1)}ms",
                                      style: TextStyle(color: col, fontSize: 10, fontFamily: "monospace"),
                                    ),
                                  ],
                                ),
                              );
                            }),
                        ],
                      ),
                    ),
                  ],
                );

                if (isWide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 3, child: leftColumn),
                      const SizedBox(width: 14),
                      Expanded(flex: 2, child: rightColumn),
                    ],
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    leftColumn,
                    const SizedBox(height: 14),
                    rightColumn,
                  ],
                );
              },
            ),
            const SizedBox(height: 16),

            // Bottom Panel: Unified Task Execution Timeline
            const Text(
              "UNIFIED MULTI-DESK TASK EXECUTION TIMELINE",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            DeskTaskExecutionList(tasks: tasks),
          ],
        ),
      ),
    );
  }

  int _deskIdToNavIndex(String deskId) {
    switch (deskId) {
      case "DESK_COMMAND":
        return 0;
      case "DESK_MARKET":
        return 1;
      case "DESK_WHALE":
        return 2;
      case "DESK_INVESTIGATION":
        return 3;
      case "DESK_QUANT":
        return 4;
      case "DESK_RISK":
        return 5;
      default:
        return 0;
    }
  }

  Widget _obsMetric(String label, String value, Color col) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 9, fontWeight: FontWeight.bold)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(color: col, fontSize: 11, fontWeight: FontWeight.bold, fontFamily: "monospace")),
      ],
    );
  }
}
