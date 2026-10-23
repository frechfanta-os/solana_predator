import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';
import 'desk_components.dart';

class TokenInvestigationView extends ConsumerStatefulWidget {
  const TokenInvestigationView({super.key});

  @override
  ConsumerState<TokenInvestigationView> createState() => _TokenInvestigationViewState();
}

class _TokenInvestigationViewState extends ConsumerState<TokenInvestigationView> {
  final TextEditingController _mintController = TextEditingController(
    text: "So11111111111111111111111111111111111111112",
  );

  @override
  void dispose() {
    _mintController.dispose();
    super.dispose();
  }

  bool _isValidBase58Mint(String s) {
    final reg = RegExp(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$');
    return reg.hasMatch(s.trim());
  }

  @override
  Widget build(BuildContext context) {
    final tokens = ref.watch(tokensProvider);
    final events = ref.watch(eventsProvider);
    final tasks = ref.watch(deskTasksProvider).where((t) => t.deskId == "DESK_INVESTIGATION").toList();
    final reports = ref.watch(deskReportsProvider).where((r) => r.deskId == "DESK_INVESTIGATION").toList();

    final mintText = _mintController.text.trim();
    final isMintValid = _isValidBase58Mint(mintText);

    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const DeskWorkspaceHeader(deskId: "DESK_INVESTIGATION"),
            const SizedBox(height: 12),

            // Evidence Disclaimer Banner
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppTheme.borderCol),
              ),
              child: const Row(
                children: [
                  Icon(Icons.verified_user_outlined, size: 16, color: AppTheme.solanaCyan),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      "INVESTIGATION MANDATE: Risk flags are evidence-backed warnings derived from observed metadata and liquidity depth, never an absolute guarantee that a contract is safe.",
                      style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // On-Demand Token Mint Inspector
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
                  const Text(
                    "TOKEN MINT & POOL METADATA INSPECTOR (VET + AUDIT)",
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _mintController,
                          onChanged: (_) => setState(() {}),
                          style: const TextStyle(fontSize: 12, fontFamily: "monospace"),
                          decoration: InputDecoration(
                            isDense: true,
                            border: const OutlineInputBorder(),
                            labelText: "Solana Base58 Token Mint",
                            errorText: mintText.isEmpty || isMintValid ? null : "Invalid Base58 format (expected 32-44 chars)",
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.predatorGreen,
                          foregroundColor: Colors.black,
                        ),
                        onPressed: isMintValid
                            ? () => ref.read(terminalControllerProvider).runDeskNow("DESK_INVESTIGATION", tokenMint: mintText)
                            : null,
                        icon: const Icon(Icons.search, size: 16),
                        label: const Text("Investigate Mint", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),

            // Discovered Token Metadata & Provider Comparison Table
            const Text(
              "OBSERVED TOKEN REGISTRY & PROVIDER PROVENANCE COMPARISON",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (tokens.isEmpty)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceBg,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppTheme.borderCol),
                ),
                child: const Text(
                  "No tokens in registry yet. Trigger a replay or run an investigation cycle above.",
                  style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                ),
              )
            else
              ...tokens.take(8).map((tok) {
                final tokEvents = events.where((e) => e.tokenMint == tok.mint).toList();
                final latestEv = tokEvents.firstOrNull;
                final hasMissing = latestEv == null || latestEv.priceUsd == null || latestEv.liquidityUsd == null;
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
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
                          Text(
                            "${tok.symbol ?? 'UNKNOWN'} (${tok.mint})",
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12, fontFamily: "monospace"),
                          ),
                          Text(
                            "Lifecycle: ${tok.currentLifecycleState}",
                            style: const TextStyle(color: AppTheme.solanaCyan, fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 16,
                        runSpacing: 4,
                        children: [
                          Text(
                            "Initial Liq: ${tok.initialLiquidityUsd != null ? '\$${tok.initialLiquidityUsd!.toStringAsFixed(0)}' : 'MISSING'}",
                            style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                          ),
                          Text(
                            "Latest Source: ${latestEv?.source ?? 'NONE'}",
                            style: const TextStyle(fontSize: 11, color: AppTheme.predatorGreen),
                          ),
                          Text(
                            "Quality: ${latestEv?.quality ?? 'UNVERIFIED'} (${latestEv != null ? '${latestEv.freshnessSeconds.toStringAsFixed(1)}s' : 'N/A'})",
                            style: TextStyle(
                              fontSize: 11,
                              color: (latestEv?.freshnessSeconds ?? 0) > 30 ? AppTheme.warningOrange : AppTheme.textBright,
                            ),
                          ),
                          if (hasMissing)
                            const Text(
                              "WARNING: Partial/Missing market fields",
                              style: TextStyle(fontSize: 11, color: AppTheme.warningOrange, fontWeight: FontWeight.bold),
                            ),
                        ],
                      ),
                    ],
                  ),
                );
              }),
            const SizedBox(height: 14),

            const Text(
              "STRUCTURED INVESTIGATION REPORTS (VET & AUDIT)",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            if (reports.isEmpty)
              const Text("No investigation reports generated yet.", style: TextStyle(color: AppTheme.textMuted, fontSize: 11))
            else
              ...reports.take(8).map((r) => StructuredReportCard(report: r)),

            const SizedBox(height: 14),
            const Text(
              "DESK 3 TASK EXECUTION HISTORY",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.solanaCyan),
            ),
            const SizedBox(height: 8),
            DeskTaskExecutionList(tasks: tasks),
          ],
        ),
      ),
    );
  }
}
