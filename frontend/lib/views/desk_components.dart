import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../models/app_models.dart';
import '../providers/app_providers.dart';

String formatLocalTimestamp(double? unixSeconds) {
  if (unixSeconds == null || unixSeconds <= 0) return "NEVER";
  final dt = DateTime.fromMillisecondsSinceEpoch((unixSeconds * 1000).toInt()).toLocal();
  final hh = dt.hour.toString().padLeft(2, '0');
  final mm = dt.minute.toString().padLeft(2, '0');
  final ss = dt.second.toString().padLeft(2, '0');
  return "$hh:$mm:$ss";
}

Color statusColorForState(String state) {
  switch (state.toUpperCase()) {
    case "RUNNING":
      return AppTheme.solanaCyan;
    case "COMPLETED":
    case "IDLE":
    case "AVAILABLE":
    case "HEALTHY":
      return AppTheme.predatorGreen;
    case "PAUSED":
    case "QUEUED":
    case "SKIPPED":
    case "STALE":
      return AppTheme.warningOrange;
    case "FAILED":
    case "VETO":
    case "UNAVAILABLE":
      return AppTheme.dangerRed;
    default:
      return AppTheme.textMuted;
  }
}

class DeskWorkspaceHeader extends ConsumerWidget {
  final String deskId;
  final Widget? trailingExtra;

  const DeskWorkspaceHeader({
    super.key,
    required this.deskId,
    this.trailingExtra,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final desks = ref.watch(desksProvider);
    final desk = desks.where((d) => d.deskId == deskId).firstOrNull ??
        DeskItem(
          deskId: deskId,
          name: deskId,
          supervisor: "Supervisor",
          description: "",
          status: "IDLE",
          isPaused: false,
          agents: const [],
          pollingIntervalSec: 15.0,
          activeTasks: 0,
          queuedTasks: 0,
          completedTasks: 0,
          failedTasks: 0,
          skippedTasks: 0,
          retryCount: 0,
          lastDurationMs: 0.0,
          hasStaleData: false,
          hasMissingData: false,
        );

    final stCol = statusColorForState(desk.isPaused ? "PAUSED" : desk.status);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 12,
            runSpacing: 8,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(color: stCol, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    desk.name.toUpperCase(),
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textBright,
                      letterSpacing: 1.1,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: stCol.withValues(alpha: 0.15),
                      border: Border.all(color: stCol),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      desk.isPaused ? "PAUSED" : desk.status,
                      style: TextStyle(color: stCol, fontSize: 10, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  ?trailingExtra,
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.solanaCyan,
                      side: const BorderSide(color: AppTheme.solanaCyan),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    ),
                    onPressed: desk.isPaused
                        ? null
                        : () => ref.read(terminalControllerProvider).runDeskNow(desk.deskId),
                    icon: const Icon(Icons.play_arrow, size: 15),
                    label: const Text("Run Cycle", style: TextStyle(fontSize: 11)),
                  ),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: desk.isPaused ? AppTheme.predatorGreen : AppTheme.cardBg,
                      foregroundColor: desk.isPaused ? Colors.black : AppTheme.warningOrange,
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    ),
                    onPressed: () {
                      if (desk.isPaused) {
                        ref.read(terminalControllerProvider).resumeDesk(desk.deskId);
                      } else {
                        ref.read(terminalControllerProvider).pauseDesk(desk.deskId);
                      }
                    },
                    icon: Icon(desk.isPaused ? Icons.play_circle : Icons.pause_circle, size: 15),
                    label: Text(desk.isPaused ? "Resume Desk" : "Pause Desk", style: const TextStyle(fontSize: 11)),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(desk.description, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 16,
            runSpacing: 6,
            children: [
              _metaChip("Supervisor", desk.supervisor, AppTheme.solanaCyan),
              _metaChip("Agents", desk.agents.join(", "), AppTheme.predatorGreen),
              _metaChip("Active / Queued", "${desk.activeTasks} / ${desk.queuedTasks}", AppTheme.textBright),
              _metaChip("Completed / Failed", "${desk.completedTasks} / ${desk.failedTasks}", desk.failedTasks > 0 ? AppTheme.dangerRed : AppTheme.predatorGreen),
              _metaChip("Retries / Skipped", "${desk.retryCount} / ${desk.skippedTasks}", AppTheme.textMuted),
              _metaChip("Last Run", formatLocalTimestamp(desk.lastExecutionAt), AppTheme.textBright),
              _metaChip("Duration", "${desk.lastDurationMs.toStringAsFixed(1)} ms", AppTheme.solanaCyan),
              _metaChip("Provenance", desk.lastSource ?? "AWAITING_FEED", AppTheme.textBright),
            ],
          ),
          if (desk.hasStaleData || desk.hasMissingData || desk.lastErrorMessage != null) ...[
            const SizedBox(height: 8),
            StaleOrMissingWarningBanner(
              hasStale: desk.hasStaleData,
              hasMissing: desk.hasMissingData,
              errorMessage: desk.lastErrorMessage,
            ),
          ],
        ],
      ),
    );
  }

  Widget _metaChip(String label, String val, Color col) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text("$label: ", style: const TextStyle(color: AppTheme.textMuted, fontSize: 10)),
        Text(val, style: TextStyle(color: col, fontSize: 10, fontWeight: FontWeight.bold, fontFamily: "monospace")),
      ],
    );
  }
}

class StaleOrMissingWarningBanner extends StatelessWidget {
  final bool hasStale;
  final bool hasMissing;
  final String? errorMessage;

  const StaleOrMissingWarningBanner({
    super.key,
    required this.hasStale,
    required this.hasMissing,
    this.errorMessage,
  });

  @override
  Widget build(BuildContext context) {
    final List<String> notices = [];
    if (hasStale) notices.add("STALE DATA OBSERVED (>30s age)");
    if (hasMissing) notices.add("PARTIAL / MISSING FIELDS (Never substituted as zero)");
    if (errorMessage != null && errorMessage!.isNotEmpty) notices.add("ERROR: $errorMessage");

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.warningOrange.withValues(alpha: 0.12),
        border: Border.all(color: AppTheme.warningOrange.withValues(alpha: 0.6)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, size: 15, color: AppTheme.warningOrange),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              notices.join("  •  "),
              style: const TextStyle(color: AppTheme.warningOrange, fontSize: 10, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }
}

class StructuredReportCard extends StatelessWidget {
  final DeskReportItem report;

  const StructuredReportCard({super.key, required this.report});

  @override
  Widget build(BuildContext context) {
    final decCol = report.isVeto
        ? AppTheme.dangerRed
        : report.decision == "BUY_CANDIDATE"
            ? AppTheme.predatorGreen
            : AppTheme.solanaCyan;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: report.isVeto ? AppTheme.dangerRed.withValues(alpha: 0.7) : AppTheme.borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Wrap(
                spacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    "[${report.agentId}]",
                    style: const TextStyle(color: AppTheme.solanaCyan, fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                  Text(
                    "Supervisor: ${report.supervisor}",
                    style: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: decCol.withValues(alpha: 0.15),
                      border: Border.all(color: decCol),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      report.decision,
                      style: TextStyle(color: decCol, fontSize: 9, fontWeight: FontWeight.bold),
                    ),
                  ),
                  if (report.isStale)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: AppTheme.warningOrange.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: const Text("STALE", style: TextStyle(color: AppTheme.warningOrange, fontSize: 9, fontWeight: FontWeight.bold)),
                    ),
                ],
              ),
              Text(
                "${report.source} • ${formatLocalTimestamp(report.observedAt)}",
                style: const TextStyle(color: AppTheme.textMuted, fontSize: 10, fontFamily: "monospace"),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            report.rationale,
            style: const TextStyle(color: AppTheme.textBright, fontSize: 11, fontWeight: FontWeight.w500),
          ),
          if (report.observedFacts.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              "OBSERVED FACTS: ${report.observedFacts.join(' | ')}",
              style: const TextStyle(color: AppTheme.predatorGreen, fontSize: 10),
            ),
          ],
          if (report.inferredConclusions.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              "INFERRED: ${report.inferredConclusions.join(' | ')}",
              style: const TextStyle(color: AppTheme.solanaCyan, fontSize: 10),
            ),
          ],
          if (report.unknownOrMissing.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              "MISSING FIELDS: ${report.unknownOrMissing.join(', ')}",
              style: const TextStyle(color: AppTheme.warningOrange, fontSize: 10),
            ),
          ],
          if (report.riskFlags.isNotEmpty || report.contradictions.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              "FLAGS: ${[...report.riskFlags, ...report.contradictions].join(' • ')}",
              style: const TextStyle(color: AppTheme.dangerRed, fontSize: 10, fontWeight: FontWeight.bold),
            ),
          ],
        ],
      ),
    );
  }
}

class DeskTaskExecutionList extends StatelessWidget {
  final List<DeskTaskItem> tasks;

  const DeskTaskExecutionList({super.key, required this.tasks});

  @override
  Widget build(BuildContext context) {
    if (tasks.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surfaceBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AppTheme.borderCol),
        ),
        child: const Center(
          child: Text("No task executions recorded for this desk yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11)),
        ),
      );
    }

    return Column(
      children: tasks.take(12).map((t) {
        final col = statusColorForState(t.status);
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
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          "[${t.agentId}] ",
                          style: const TextStyle(color: AppTheme.solanaCyan, fontWeight: FontWeight.bold, fontSize: 11),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: col.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(3),
                          ),
                          child: Text(t.status, style: TextStyle(color: col, fontSize: 9, fontWeight: FontWeight.bold)),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            t.outputSummary,
                            style: const TextStyle(fontSize: 11, color: AppTheme.textBright),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      "Task: ${t.taskId} • Input: ${t.inputSummary} • Source: ${t.source} (${t.observationQuality})",
                      style: const TextStyle(fontSize: 9, color: AppTheme.textMuted, fontFamily: "monospace"),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text("${t.durationMs.toStringAsFixed(1)} ms", style: const TextStyle(color: AppTheme.predatorGreen, fontSize: 10, fontFamily: "monospace")),
                  Text(formatLocalTimestamp(t.startedAt), style: const TextStyle(color: AppTheme.textMuted, fontSize: 9)),
                ],
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}
