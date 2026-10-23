import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class DataSourcesView extends ConsumerWidget {
  const DataSourcesView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final providersHealth = ref.watch(providersHealthProvider);
    final sysHealth = ref.watch(systemHealthProvider);
    final providersMap = (providersHealth["providers"] as Map<String, dynamic>?) ?? {};
    final llmStatus = (sysHealth["llm"] as Map<String, dynamic>?) ?? {};

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "DATA SOURCES & COMPOSITE FAILOVER TELEMETRY",
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan, letterSpacing: 1.1),
                      ),
                      SizedBox(height: 4),
                      Text(
                        "Failover Chain: GMGN (Optional) -> Mobula (Optional) -> DEX Screener (Primary) -> Solana RPC (On-Chain Truth)",
                        style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                      ),
                    ],
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: () {
                    ref.read(terminalControllerProvider).fetchProvidersHealth();
                    ref.read(terminalControllerProvider).fetchSystemHealth();
                  },
                  icon: const Icon(Icons.refresh, size: 15),
                  label: const Text("Probe Providers", style: TextStyle(fontSize: 11)),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Provider Cards
            _providerCard(
              name: "DEX Screener Public REST API",
              role: "Primary Market Quotation Source (USD Price, Liquidity, 24h Volume)",
              data: providersMap["dex_screener"] as Map<String, dynamic>?,
              defaultStatus: "AVAILABLE (READ-ONLY)",
              isAvailableDefault: true,
            ),
            _providerCard(
              name: "Solana Mainnet-Beta Read-Only RPC",
              role: "On-Chain Truth (Slot, BlockTime, Signatures — Never fabricates USD price)",
              data: providersMap["solana_rpc"] as Map<String, dynamic>?,
              defaultStatus: "AVAILABLE (ON-CHAIN ONLY)",
              isAvailableDefault: true,
            ),
            _providerCard(
              name: "GMGN OpenAPI Adapter",
              role: "Optional Provider (Disabled by default; requires >= \$100 on-chain balance for API key)",
              data: providersMap["gmgn"] as Map<String, dynamic>?,
              defaultStatus: "DISABLED / RESTRICTED (60s Cooldown Policy)",
              isAvailableDefault: false,
            ),
            _providerCard(
              name: "Mobula REST Adapter (chainId=solana)",
              role: "Optional Provider (Disabled by default; Free plan returns HTTP 403 Forbidden)",
              data: providersMap["mobula"] as Map<String, dynamic>?,
              defaultStatus: "DISABLED / PLAN RESTRICTED (0 Network Calls when disabled)",
              isAvailableDefault: false,
            ),
            const SizedBox(height: 16),

            // LLM Advisory Status Card
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppTheme.borderCol),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "LLM MULTI-MODEL ADVISORY CLIENT (OPENROUTER / GLM-5.3-FLASH)",
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    "State: ${llmStatus['availability_state'] ?? 'STANDBY'} • Model: ${llmStatus['model'] ?? 'glm-5.3-flash'} • Calls: ${llmStatus['call_count'] ?? 0}",
                    style: const TextStyle(fontSize: 11, color: AppTheme.textBright, fontFamily: "monospace"),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    "Safety Invariant: Deterministic agents continue uninterrupted if LLM is disabled or rate-limited. LLM cannot execute tools or override RISK vetoes.",
                    style: TextStyle(fontSize: 11, color: AppTheme.textMuted),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _providerCard({
    required String name,
    required String role,
    required Map<String, dynamic>? data,
    required String defaultStatus,
    required bool isAvailableDefault,
  }) {
    final avail = data != null ? (data["available"] == true) : isAvailableDefault;
    final configured = data != null ? (data["configured"] == true) : isAvailableDefault;
    final reason = data?["reason"]?.toString() ?? defaultStatus;
    final col = avail ? AppTheme.predatorGreen : AppTheme.warningOrange;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
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
              Text(name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: col.withValues(alpha: 0.15),
                  border: Border.all(color: col),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  avail ? "AVAILABLE" : (configured ? "RESTRICTED" : "DISABLED"),
                  style: TextStyle(color: col, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(role, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
          const SizedBox(height: 6),
          Text(
            "Telemetry: $reason",
            style: const TextStyle(color: AppTheme.solanaCyan, fontSize: 10, fontFamily: "monospace"),
          ),
        ],
      ),
    );
  }
}
