import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class ConfigRiskView extends ConsumerStatefulWidget {
  const ConfigRiskView({super.key});

  @override
  ConsumerState<ConfigRiskView> createState() => _ConfigRiskViewState();
}

class _ConfigRiskViewState extends ConsumerState<ConfigRiskView> {
  late TextEditingController _urlController;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: ref.read(backendUrlProvider));
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "TERMINAL CONFIGURATION & RISK LIMITS",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.solanaCyan,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 16),
            // Backend URL Setup
            Card(
              color: AppTheme.surfaceBg,
              shape: RoundedRectangleBorder(
                side: const BorderSide(color: AppTheme.borderCol),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text("BACKEND SERVICE URL", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 6),
                    const Text(
                      "For Android emulator use http://10.0.2.2:8000. For desktop/web terminal use http://127.0.0.1:8000.",
                      style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _urlController,
                            style: const TextStyle(fontSize: 13, fontFamily: "monospace"),
                            decoration: const InputDecoration(
                              isDense: true,
                              border: OutlineInputBorder(),
                              hintText: "http://127.0.0.1:8000",
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(backgroundColor: AppTheme.predatorGreen, foregroundColor: Colors.black),
                          onPressed: () {
                            ref.read(terminalControllerProvider).updateBackendUrl(_urlController.text.trim());
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text("Backend URL updated. Reconnecting WebSocket...")),
                            );
                          },
                          child: const Text("Apply URL"),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            // Deterministic Replay Trigger
            Card(
              color: AppTheme.surfaceBg,
              shape: RoundedRectangleBorder(
                side: const BorderSide(color: AppTheme.borderCol),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text("DETERMINISTIC SIMULATION REPLAY", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                        SizedBox(height: 4),
                        Text(
                          "Injects verified synthetic tokens and whale events offline.",
                          style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                        ),
                      ],
                    ),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(backgroundColor: AppTheme.solanaCyan, foregroundColor: Colors.black),
                      onPressed: () async {
                        final messenger = ScaffoldMessenger.of(context);
                        final ok = await ref.read(terminalControllerProvider).triggerReplay();
                        messenger.showSnackBar(
                          SnackBar(content: Text(ok ? "Replay events injected successfully!" : "Failed to inject replay.")),
                        );
                      },
                      icon: const Icon(Icons.play_circle_filled, size: 18),
                      label: const Text("Run Replay"),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            // Strict Risk Limits
            const Text("HARD RISK INVARIANTS (INVIOLABLE)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.warningOrange)),
            const SizedBox(height: 8),
            _buildRuleRow("Absolute Risk Veto Power", "Active (RISK agent has unconditional veto over all decisions)"),
            _buildRuleRow("Maximum Portfolio Drawdown Veto", "15.0% (Triggers circuit breaker halt)"),
            _buildRuleRow("Maximum Concurrent Open Positions", "5 slots"),
            _buildRuleRow("Maximum Allocation Per Token", "10.0% of virtual equity (capped at 1% pool depth)"),
            _buildRuleRow("Simulated Taker Fee", "25 bps (0.25%)"),
            _buildRuleRow("Simulated Base Slippage", "30 bps (0.30%) + depth impact factor"),
            _buildRuleRow("Data Staleness Threshold", "30.0 seconds"),
            _buildRuleRow("Live Transaction Submission Logic", "DISABLED & REMOVED (Zero keys, Zero RPC writes)"),
          ],
        ),
      ),
    );
  }

  Widget _buildRuleRow(String rule, String val) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      margin: const EdgeInsets.only(bottom: 6),
      decoration: BoxDecoration(
        color: AppTheme.surfaceBg,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppTheme.borderCol),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(rule, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
          Text(val, style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
        ],
      ),
    );
  }
}
