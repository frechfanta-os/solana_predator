import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

class RiskSkepticView extends ConsumerWidget {
  const RiskSkepticView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final portfolio = ref.watch(portfolioProvider);
    final sysHealth = ref.watch(systemHealthProvider);
    final riskAudits = ref.watch(riskAuditProvider);
    final tasks = ref.watch(deskTasksProvider).where((t) => t.deskId == "DESK_RISK").toList();
    final reports = ref.watch(deskReportsProvider).where((r) => r.deskId == "DESK_RISK").toList();
    final allVetoes = ref.watch(deskReportsProvider).where((r) => r.isVeto).toList();

    final killSwitchActive = sysHealth["emergency_kill_switch_active"] == true;
    final currentDd = (portfolio?.currentDrawdownPct ?? 0.0) * 100.0;
    final maxDd = (portfolio?.maxDrawdownPct ?? 0.0) * 100.0;
    final openPosCount = portfolio?.openPositionsCount ?? 0;

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const DeskWorkspaceHeader(deskId: "DESK_RISK"),
            const SizedBox(height: 12),

            // Authoritative RISK Veto Banner + Emergency Simulation Stop
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: killSwitchActive ? AppTheme.dangerRed.withValues(alpha: 0.15) : AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: killSwitchActive ? AppTheme.dangerRed : AppTheme.warningOrange),
              ),
              child: Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 12,
                runSpacing: 10,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.gpp_maybe,
                            color: killSwitchActive ? AppTheme.dangerRed : AppTheme.warningOrange,
                            size: 18,
                          ),
                          const SizedBox(width: 8),
                          const Text(
                            "CRITICAL INVARIANT: BACKEND RISK VETO IS AUTHORITATIVE",
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppTheme.warningOrange),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        "Neither CHIEF, another agent, an LLM advisory, nor any UI control can override a RISK veto.",
                        style: TextStyle(fontSize: 11, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: killSwitchActive ? AppTheme.predatorGreen : AppTheme.dangerRed,
                      foregroundColor: Colors.black,
                    ),
                    onPressed: () => ref.read(terminalControllerProvider).toggleEmergencyKillSwitch(!killSwitchActive),
                    icon: Icon(killSwitchActive ? Icons.lock_open : Icons.dangerous, size: 16),
                    label: Text(
                      killSwitchActive ? "Disengage Kill-Switch" : "ENGAGE EMERGENCY KILL-SWITCH",
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),

            // Exposure & Simulation Limits Overview
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                _riskBox("CURRENT DRAWDOWN", "${currentDd.toStringAsFixed(2)}% / 15.0% Max", currentDd >= 15 ? AppTheme.dangerRed : AppTheme.predatorGreen),
                _riskBox("PEAK DRAWDOWN", "${maxDd.toStringAsFixed(2)}%", maxDd >= 15 ? AppTheme.dangerRed : AppTheme.textBright),
                _riskBox("OPEN POSITIONS", "$openPosCount / 5 Slots", openPosCount >= 5 ? AppTheme.warningOrange : AppTheme.solanaCyan),
                _riskBox("VETOES ISSUED", "${allVetoes.length}", allVetoes.isNotEmpty ? AppTheme.dangerRed : AppTheme.predatorGreen),
                _riskBox("MAX ALLOCATION", "10% Equity / 1% Pool Liq", AppTheme.textBright),
              ],
            ),
            const SizedBox(height: 16),

            // Veto & Contradiction History
            const Text(
              "RISK VETOES & SKEPTIC CONTRADICTION REPORTS (RISK · SKEPTIC · SIZE)",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (reports.isEmpty && allVetoes.isEmpty)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceBg,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppTheme.borderCol),
                ),
                child: const Text(
                  "No risk or skeptic reports recorded yet. Run a cycle or replay to inspect contrarian checks.",
                  style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                ),
              )
            else
              ...(reports.isNotEmpty ? reports.take(8) : allVetoes.take(8))
                  .map((r) => StructuredReportCard(report: r)),

            const SizedBox(height: 14),
            const Text(
              "13-POINT INDEPENDENT SERVER RISK AUDIT LOG",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (riskAudits.isEmpty)
              const Text("No independent risk guard checks logged yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
            else
              ...riskAudits.take(8).map((a) {
                final passed = a["passed"] == 1 || a["passed"] == true;
                return Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceBg,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppTheme.borderCol),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        "${a['check_name']} (${passed ? 'PASS' : 'BLOCKED'})",
                        style: TextStyle(
                          color: passed ? AppTheme.predatorGreen : AppTheme.dangerRed,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        "Observed: ${a['observed_val']} (Bound: ${a['threshold_val']})",
                        style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
                      ),
                    ],
                  ),
                );
              }),

            const SizedBox(height: 14),
            const Text(
              "DESK 5 TASK EXECUTION HISTORY",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            DeskTaskExecutionList(tasks: tasks),
          ],
        ),
      ),
    );
  }

  Widget _riskBox(String label, String val, Color col) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 9, color: AppTheme.textMuted, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(val, style: TextStyle(fontSize: 13, color: col, fontWeight: FontWeight.bold, fontFamily: "monospace")),
        ],
      ),
    );
  }
}
