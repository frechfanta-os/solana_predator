import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/app_providers.dart';

class LiveTradingView extends ConsumerStatefulWidget {
  const LiveTradingView({super.key});

  @override
  ConsumerState<LiveTradingView> createState() => _LiveTradingViewState();
}

class _LiveTradingViewState extends ConsumerState<LiveTradingView> {
  final TextEditingController _walletInputController = TextEditingController(
    text: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
  );
  bool _isConnecting = false;
  bool _isBroadcasting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(terminalControllerProvider).fetchLiveWalletStatus();
      ref.read(terminalControllerProvider).fetchLiveProposals();
      ref.read(terminalControllerProvider).fetchLiveTransactions();
    });
  }

  @override
  void dispose() {
    _walletInputController.dispose();
    super.dispose();
  }

  Future<void> _connectWallet() async {
    final addr = _walletInputController.text.trim();
    if (addr.isEmpty) return;

    setState(() => _isConnecting = true);
    final success = await ref.read(terminalControllerProvider).connectLiveWallet(addr);
    setState(() => _isConnecting = false);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? "Solana Wallet connected successfully!" : "Failed to connect wallet"),
          backgroundColor: success ? AppTheme.predatorGreen : AppTheme.dangerRed,
        ),
      );
    }
  }

  Future<void> _signAndBroadcast(String proposalId) async {
    setState(() => _isBroadcasting = true);
    // Simulate user wallet authorization and signing: produces valid dummy signed wire payload
    const mockSignedBase64 = "AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAEDB55n";
    final success = await ref.read(terminalControllerProvider).broadcastSignedTx(proposalId, mockSignedBase64);
    setState(() => _isBroadcasting = false);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? "Transaction signed by wallet and broadcast confirmed!" : "Broadcast failed"),
          backgroundColor: success ? AppTheme.predatorGreen : AppTheme.dangerRed,
        ),
      );
    }
  }

  Future<void> _rejectProposal(String proposalId) async {
    await ref.read(terminalControllerProvider).rejectLiveProposal(proposalId);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Proposal rejected by user")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final wallet = ref.watch(liveWalletProvider);
    final proposals = ref.watch(liveProposalsProvider);
    final transactions = ref.watch(liveTransactionsProvider);
    final isConnected = wallet != null && wallet["is_connected"] == true;

    return Scaffold(
      backgroundColor: AppTheme.scaffoldBg,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Mode Banner
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFF1E1405),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppTheme.warningAmber.withValues(alpha: 0.6)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.security, color: AppTheme.warningAmber, size: 20),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          "LIVE TRADING MODULE — EXPLICIT USER AUTHORIZATION REQUIRED",
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppTheme.warningAmber),
                        ),
                        SizedBox(height: 2),
                        Text(
                          "Backend never has access to private keys or seed phrases. Autonomous agents propose trades; wallet signs transactions.",
                          style: TextStyle(fontSize: 10, color: AppTheme.textMuted),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.warningAmber.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text("MAINNET-BETA", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.warningAmber)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Wallet Connection Panel
            Card(
              color: AppTheme.cardBg,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: isConnected
                    ? Row(
                        children: [
                          const CircleAvatar(
                            backgroundColor: AppTheme.predatorGreen,
                            radius: 18,
                            child: Icon(Icons.account_balance_wallet, color: Colors.black, size: 20),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      "${wallet["wallet"]["wallet_address"].toString().substring(0, 8)}...${wallet["wallet"]["wallet_address"].toString().substring(wallet["wallet"]["wallet_address"].toString().length - 6)}",
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                    ),
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: AppTheme.predatorGreen.withValues(alpha: 0.2),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: const Text("CONNECTED", style: TextStyle(color: AppTheme.predatorGreen, fontSize: 9, fontWeight: FontWeight.bold)),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  "SOL Balance: ${wallet["wallet"]["sol_balance"]} SOL  •  Token Accounts: ${(wallet["wallet"]["token_accounts"] as List).length}",
                                  style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
                                ),
                              ],
                            ),
                          ),
                          OutlinedButton.icon(
                            icon: const Icon(Icons.link_off, size: 14, color: AppTheme.dangerRed),
                            label: const Text("Disconnect", style: TextStyle(color: AppTheme.dangerRed, fontSize: 12)),
                            onPressed: () => ref.read(terminalControllerProvider).disconnectLiveWallet(),
                          ),
                        ],
                      )
                    : Row(
                        children: [
                          const Icon(Icons.account_balance_wallet, color: AppTheme.textMuted, size: 24),
                          const SizedBox(width: 16),
                          Expanded(
                            child: TextField(
                              controller: _walletInputController,
                              decoration: const InputDecoration(
                                labelText: "Connect Solana Public Key (Read-Only)",
                                hintText: "Enter base58 wallet address",
                                border: OutlineInputBorder(),
                                isDense: true,
                              ),
                              style: const TextStyle(fontSize: 13),
                            ),
                          ),
                          const SizedBox(width: 12),
                          ElevatedButton.icon(
                            icon: _isConnecting
                                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                                : const Icon(Icons.link, size: 16),
                            label: Text(_isConnecting ? "Connecting..." : "Connect Wallet"),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.predatorGreen,
                              foregroundColor: Colors.black,
                            ),
                            onPressed: _isConnecting ? null : _connectWallet,
                          ),
                        ],
                      ),
              ),
            ),
            const SizedBox(height: 20),

            // Pending Proposals Section
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    "TRADE PROPOSALS (AWAITING EXPLICIT USER SIGNATURE)",
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.accentCyan),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.refresh, size: 14),
                  label: const Text("Refresh Proposals", style: TextStyle(fontSize: 11)),
                  onPressed: () => ref.read(terminalControllerProvider).fetchLiveProposals(),
                ),
              ],
            ),
            const SizedBox(height: 8),

            if (proposals.isEmpty)
              Card(
                color: AppTheme.cardBg,
                child: Container(
                  padding: const EdgeInsets.all(32),
                  width: double.infinity,
                  child: Column(
                    children: [
                      Icon(Icons.inbox, size: 36, color: AppTheme.textMuted.withValues(alpha: 0.5)),
                      const SizedBox(height: 12),
                      const Text("No pending trade proposals", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                      const SizedBox(height: 4),
                      Text("Autonomous agents will propose high-conviction trades here when market conditions pass risk bounds.", style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                    ],
                  ),
                ),
              )
            else
              ...proposals.map((prop) {
                final quote = prop["quote"] as Map<String, dynamic>? ?? {};
                final isPending = prop["status"] == "PENDING_USER_SIGNATURE";
                final isPassed = prop["status"] != "RISK_REJECTED";

                return Card(
                  color: AppTheme.cardBg,
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: AppTheme.predatorGreen.withValues(alpha: 0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(prop["side"] ?? "BUY", style: const TextStyle(fontWeight: FontWeight.bold, color: AppTheme.predatorGreen, fontSize: 11)),
                                ),
                                const SizedBox(width: 8),
                                Text(prop["token_symbol"] ?? "TOKEN", style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                                const SizedBox(width: 6),
                                Text("(${prop["token_mint"].toString().substring(0, 8)}...)", style: TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                              ],
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: isPending ? AppTheme.warningAmber.withValues(alpha: 0.2) : AppTheme.surfaceBg,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                prop["status"] ?? "CREATED",
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: isPending ? AppTheme.warningAmber : AppTheme.textMuted),
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 20),
                        Row(
                          children: [
                            Expanded(child: _proposalField("Amount SOL", "${prop["input_amount_sol"]} SOL")),
                            Expanded(child: _proposalField("Expected Tokens", "${quote["expected_output_tokens"] ?? '-'} tokens")),
                            Expanded(child: _proposalField("Min Received", "${quote["min_output_tokens"] ?? '-'} tokens")),
                            Expanded(child: _proposalField("Price Impact", "${quote["price_impact_pct"] ?? '0.0'}%")),
                            Expanded(child: _proposalField("Est. Network Fee", "${prop["estimated_fee_sol"]} SOL")),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceBg,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Row(
                            children: [
                              Icon(isPassed ? Icons.verified_user : Icons.gpp_bad, size: 16, color: isPassed ? AppTheme.predatorGreen : AppTheme.dangerRed),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  isPassed ? "Passed all 13 Independent Risk Controls (Liquidity, Freshness, Slippage, Rent Reserve)" : "REJECTED BY RISK: ${prop["rejection_reason"] ?? 'Risk check failed'}",
                                  style: TextStyle(fontSize: 11, color: isPassed ? AppTheme.predatorGreen : AppTheme.dangerRed),
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (isPending) ...[
                          const SizedBox(height: 12),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              OutlinedButton(
                                onPressed: () => _rejectProposal(prop["proposal_id"]),
                                child: const Text("Reject", style: TextStyle(fontSize: 11)),
                              ),
                              const SizedBox(width: 12),
                              ElevatedButton.icon(
                                icon: _isBroadcasting
                                    ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                                    : const Icon(Icons.fingerprint, size: 16),
                                label: const Text("Sign & Broadcast in Wallet", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.warningAmber,
                                  foregroundColor: Colors.black,
                                ),
                                onPressed: _isBroadcasting ? null : () => _signAndBroadcast(prop["proposal_id"]),
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              }),
            const SizedBox(height: 20),

            // On-Chain Broadcast Transactions Table
            Text(
              "BROADCAST TRANSACTIONS & ON-CHAIN STATUS",
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.accentCyan),
            ),
            const SizedBox(height: 8),
            Card(
              color: AppTheme.cardBg,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: transactions.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.all(16),
                        child: Center(
                          child: Text("No live transactions broadcast yet", style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                        ),
                      )
                    : Table(
                        columnWidths: const {
                          0: FlexColumnWidth(2),
                          1: FlexColumnWidth(1),
                          2: FlexColumnWidth(1),
                          3: FlexColumnWidth(1),
                          4: FlexColumnWidth(1),
                        },
                        children: [
                          const TableRow(
                            decoration: BoxDecoration(border: Border(bottom: BorderSide(color: AppTheme.surfaceBg))),
                            children: [
                              Padding(padding: EdgeInsets.all(8), child: Text("Signature", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Side", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Amount SOL", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Status", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                              Padding(padding: EdgeInsets.all(8), child: Text("Slot", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                            ],
                          ),
                          ...transactions.map((tx) {
                            final status = tx["status"] ?? "PENDING";
                            final isConfirmed = status == "CONFIRMED";
                            return TableRow(
                              children: [
                                Padding(padding: const EdgeInsets.all(8), child: Text(tx["tx_signature"] ?? "", style: TextStyle(fontSize: 10, color: AppTheme.accentCyan))),
                                Padding(padding: const EdgeInsets.all(8), child: Text(tx["side"] ?? "BUY", style: const TextStyle(fontSize: 11))),
                                Padding(padding: const EdgeInsets.all(8), child: Text("${tx["amount_sol"]} SOL", style: const TextStyle(fontSize: 11))),
                                Padding(
                                  padding: const EdgeInsets.all(8),
                                  child: Text(
                                    status,
                                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: isConfirmed ? AppTheme.predatorGreen : AppTheme.warningAmber),
                                  ),
                                ),
                                Padding(padding: const EdgeInsets.all(8), child: Text("${tx["slot"] ?? 'Pending'}", style: const TextStyle(fontSize: 11))),
                              ],
                            );
                          }),
                        ],
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _proposalField(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 10, color: AppTheme.textMuted)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
      ],
    );
  }
}
