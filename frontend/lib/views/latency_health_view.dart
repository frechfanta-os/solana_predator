import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class LatencyHealthView extends ConsumerWidget {
  const LatencyHealthView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(healthMetricsProvider);

    final uptime = health['uptime_seconds'] ?? 0.0;
    final totalEvents = health['total_events_received'] ?? 0;
    final duplicates = health['duplicate_events_filtered'] ?? 0;
    final errors = health['total_errors'] ?? 0;
    
    final latencies = health['latencies_ms'] as Map<String, dynamic>? ?? {};
    final sources = health['sources'] as Map<String, dynamic>? ?? {};

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "OBSERVABILITY — LATENCY & PIPELINE HEALTH",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 16),
            // Overall Stats
            Row(
              children: [
                Expanded(child: _buildHealthTile("UPTIME", "${(uptime / 60).toStringAsFixed(1)} min", AppTheme.textBright)),
                const SizedBox(width: 10),
                Expanded(child: _buildHealthTile("EVENTS PROCESSED", "$totalEvents", AppTheme.predatorGreen)),
                const SizedBox(width: 10),
                Expanded(child: _buildHealthTile("DUPLICATES FILTERED", "$duplicates", AppTheme.solanaCyan)),
                const SizedBox(width: 10),
                Expanded(child: _buildHealthTile("PIPELINE ERRORS", "$errors", errors > 0 ? AppTheme.dangerRed : AppTheme.predatorGreen)),
              ],
            ),
            const SizedBox(height: 24),
            const Text("STAGE LATENCY BENCHMARKS (MILLISECONDS)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.solanaCyan)),
            const SizedBox(height: 10),
            Table(
              border: TableBorder.all(color: AppTheme.borderCol),
              children: [
                const TableRow(
                  decoration: BoxDecoration(color: AppTheme.surfaceBg),
                  children: [
                    Padding(padding: EdgeInsets.all(8), child: Text("Stage", style: TextStyle(fontWeight: FontWeight.bold))),
                    Padding(padding: EdgeInsets.all(8), child: Text("p50", style: TextStyle(fontWeight: FontWeight.bold))),
                    Padding(padding: EdgeInsets.all(8), child: Text("p95", style: TextStyle(fontWeight: FontWeight.bold))),
                    Padding(padding: EdgeInsets.all(8), child: Text("p99", style: TextStyle(fontWeight: FontWeight.bold))),
                    Padding(padding: EdgeInsets.all(8), child: Text("Avg", style: TextStyle(fontWeight: FontWeight.bold))),
                  ],
                ),
                _buildLatencyRow("Ingestion", latencies['ingest']),
                _buildLatencyRow("Normalization", latencies['normalize']),
                _buildLatencyRow("Agent Analysis", latencies['agent_analysis']),
                _buildLatencyRow("End-to-End Pipeline", latencies['end_to_end']),
              ],
            ),
            const SizedBox(height: 24),
            const Text("DATA SOURCE STATUSES", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.solanaCyan)),
            const SizedBox(height: 10),
            Row(
              children: sources.entries.map((e) {
                final src = e.value as Map<String, dynamic>? ?? {};
                final status = src['status'] ?? 'UNKNOWN';
                return Expanded(
                  child: Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceBg,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppTheme.borderCol),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(e.key, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                        const SizedBox(height: 4),
                        Text(
                          status,
                          style: TextStyle(
                            color: status == 'ACTIVE' ? AppTheme.predatorGreen : AppTheme.warningOrange,
                            fontWeight: FontWeight.bold,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHealthTile(String label, String value, Color col) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 9, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(color: col, fontSize: 15, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  TableRow _buildLatencyRow(String label, dynamic data) {
    final map = data as Map<String, dynamic>? ?? {};
    return TableRow(
      children: [
        Padding(padding: const EdgeInsets.all(8), child: Text(label, style: const TextStyle(fontSize: 12))),
        Padding(padding: const EdgeInsets.all(8), child: Text("${map['p50'] ?? 0.0} ms", style: const TextStyle(fontSize: 12))),
        Padding(padding: const EdgeInsets.all(8), child: Text("${map['p95'] ?? 0.0} ms", style: const TextStyle(fontSize: 12))),
        Padding(padding: const EdgeInsets.all(8), child: Text("${map['p99'] ?? 0.0} ms", style: const TextStyle(fontSize: 12))),
        Padding(padding: const EdgeInsets.all(8), child: Text("${map['avg'] ?? 0.0} ms", style: const TextStyle(fontSize: 12))),
      ],
    );
  }
}
