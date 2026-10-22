import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:http/http.dart' as http;
import '../core/constants.dart';
import '../core/websocket_client.dart';
import '../models/app_models.dart';

// Backend URL State
final backendUrlProvider = StateProvider<String>((ref) => AppConstants.defaultHttpBase);
final wsConnectedProvider = StateProvider<bool>((ref) => false);

// Data Providers
final tokensProvider = StateProvider<List<TokenItem>>((ref) => []);
final eventsProvider = StateProvider<List<NormalizedEventItem>>((ref) => []);
final whaleActivitiesProvider = StateProvider<List<WhaleActivityItem>>((ref) => []);
final agentDecisionsProvider = StateProvider<List<AgentDecisionItem>>((ref) => []);
final positionsProvider = StateProvider<List<PositionItem>>((ref) => []);
final portfolioProvider = StateProvider<PortfolioSnapshotItem?>((ref) => null);
final healthMetricsProvider = StateProvider<Map<String, dynamic>>((ref) => {});
final learningMetricsProvider = StateProvider<Map<String, dynamic>>((ref) => {});
final liveWalletProvider = StateProvider<Map<String, dynamic>?>((ref) => null);
final liveProposalsProvider = StateProvider<List<Map<String, dynamic>>>((ref) => []);
final liveTransactionsProvider = StateProvider<List<Map<String, dynamic>>>((ref) => []);

// Controller Class for Network Actions
class TerminalController {
  final Ref ref;
  WebSocketService? _wsService;

  TerminalController(this.ref);

  void initWebSocket() {
    final baseUrl = ref.read(backendUrlProvider);
    final wsBase = baseUrl.replaceFirst("http://", "ws://").replaceFirst("https://", "wss://");
    final wsUrl = "$wsBase/ws";

    _wsService?.disconnect();
    _wsService = WebSocketService(
      wsUrl: wsUrl,
      onConnectionChanged: (connected) {
        ref.read(wsConnectedProvider.notifier).state = connected;
        if (connected) {
          refreshAll();
        }
      },
      onMessageReceived: (data) {
        _handleLivePipelineUpdate(data);
      },
    );
    _wsService!.connect();
  }

  void disconnect() {
    _wsService?.disconnect();
  }

  void dispose() {
    _wsService?.disconnect();
  }

  void updateBackendUrl(String newUrl) {
    ref.read(backendUrlProvider.notifier).state = newUrl;
    initWebSocket();
    refreshAll();
  }

  Future<void> refreshAll() async {
    await Future.wait([
      fetchTokens(),
      fetchEvents(),
      fetchWhales(),
      fetchDecisions(),
      fetchPositions(),
      fetchPortfolio(),
      fetchHealth(),
      fetchLearningMetrics(),
      fetchLiveWalletStatus(),
      fetchLiveProposals(),
      fetchLiveTransactions(),
    ]);
  }

  Future<void> fetchTokens() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/market/tokens"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(tokensProvider.notifier).state = list.map((e) => TokenItem.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<void> fetchEvents() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/market/events?limit=50"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(eventsProvider.notifier).state = list.map((e) => NormalizedEventItem.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<void> fetchWhales() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/whales?limit=50"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(whaleActivitiesProvider.notifier).state = list.map((e) => WhaleActivityItem.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<void> fetchDecisions() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/agents/decisions?limit=50"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(agentDecisionsProvider.notifier).state = list.map((e) => AgentDecisionItem.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<void> fetchPositions() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/paper/positions"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(positionsProvider.notifier).state = list.map((e) => PositionItem.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<void> fetchPortfolio() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/paper/portfolio"));
      if (res.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(res.body);
        if (data.containsKey("current_snapshot")) {
          ref.read(portfolioProvider.notifier).state = PortfolioSnapshotItem.fromJson(data["current_snapshot"]);
        }
      }
    } catch (_) {}
  }

  Future<void> fetchHealth() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/metrics"));
      if (res.statusCode == 200) {
        ref.read(healthMetricsProvider.notifier).state = json.decode(res.body);
      }
    } catch (_) {}
  }

  Future<void> fetchLearningMetrics() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/learning/metrics"));
      if (res.statusCode == 200) {
        ref.read(learningMetricsProvider.notifier).state = json.decode(res.body);
      }
    } catch (_) {}
  }

  Future<bool> triggerLearningEvaluation() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(Uri.parse("$base/api/learning/evaluate"));
      if (res.statusCode == 200) {
        await fetchLearningMetrics();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<void> fetchLiveWalletStatus() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/live/wallet/status"));
      if (res.statusCode == 200) {
        ref.read(liveWalletProvider.notifier).state = json.decode(res.body);
      }
    } catch (_) {}
  }

  Future<bool> connectLiveWallet(String address) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/live/wallet/connect"),
        headers: {"Content-Type": "application/json"},
        body: json.encode({"wallet_address": address}),
      );
      if (res.statusCode == 200) {
        await fetchLiveWalletStatus();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<void> disconnectLiveWallet() async {
    try {
      final base = ref.read(backendUrlProvider);
      await http.post(Uri.parse("$base/api/live/wallet/disconnect"));
      ref.read(liveWalletProvider.notifier).state = null;
    } catch (_) {}
  }

  Future<void> fetchLiveProposals() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/live/proposals"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(liveProposalsProvider.notifier).state = list.cast<Map<String, dynamic>>();
      }
    } catch (_) {}
  }

  Future<bool> broadcastSignedTx(String proposalId, String signedTxBase64) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/live/proposals/$proposalId/broadcast"),
        headers: {"Content-Type": "application/json"},
        body: json.encode({"signed_tx_base64": signedTxBase64}),
      );
      if (res.statusCode == 200) {
        await fetchLiveProposals();
        await fetchLiveTransactions();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<void> rejectLiveProposal(String proposalId) async {
    try {
      final base = ref.read(backendUrlProvider);
      await http.post(
        Uri.parse("$base/api/live/proposals/$proposalId/reject"),
        headers: {"Content-Type": "application/json"},
        body: json.encode({"reason": "Rejected by user"}),
      );
      await fetchLiveProposals();
    } catch (_) {}
  }

  Future<void> fetchLiveTransactions() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/live/transactions"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(liveTransactionsProvider.notifier).state = list.cast<Map<String, dynamic>>();
      }
    } catch (_) {}
  }

  Future<bool> triggerReplay() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/simulation/start_replay"),
        headers: {"X-Admin-Key": "predator-admin-auth-token-2026"},
      );
      if (res.statusCode == 200) {
        await refreshAll();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> resetPortfolio() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/paper/reset"),
        headers: {"X-Admin-Key": "predator-admin-auth-token-2026"},
      );
      if (res.statusCode == 200) {
        await refreshAll();
        return true;
      }
    } catch (_) {}
    return false;
  }

  void _handleLivePipelineUpdate(Map<String, dynamic> data) {
    if (data["type"] == "PIPELINE_UPDATE") {
      if (data["portfolio"] != null) {
        ref.read(portfolioProvider.notifier).state = PortfolioSnapshotItem.fromJson(data["portfolio"]);
      }
      if (data["open_positions"] != null) {
        final List<dynamic> posList = data["open_positions"];
        final openItems = posList.map((e) => PositionItem.fromJson(e)).toList();
        final currentClosed = ref.read(positionsProvider).where((p) => !p.isOpen).toList();
        ref.read(positionsProvider.notifier).state = [...openItems, ...currentClosed];
      }
      if (data["event"] != null) {
        final newEvent = NormalizedEventItem.fromJson(data["event"]);
        final current = ref.read(eventsProvider);
        ref.read(eventsProvider.notifier).state = [newEvent, ...current.take(49)];
      }
      if (data["decision"] != null) {
        final dec = data["decision"];
        final newDec = AgentDecisionItem(
          consensusId: dec["consensus_id"] ?? "",
          tokenMint: dec["token_mint"] ?? "",
          timestamp: (dec["timestamp"] as num?)?.toDouble() ?? 0.0,
          agentName: "CHIEF",
          decision: dec["final_decision"] ?? "PASS",
          score: null,
          confidence: 1.0,
          latencyMs: (dec["processing_total_latency_ms"] as num?)?.toDouble() ?? 0.0,
          reasonCodes: [dec["chief_reason"] ?? ""],
        );
        final current = ref.read(agentDecisionsProvider);
        ref.read(agentDecisionsProvider.notifier).state = [newDec, ...current.take(49)];
      }
    }
  }
}

final terminalControllerProvider = Provider<TerminalController>((ref) => TerminalController(ref));
