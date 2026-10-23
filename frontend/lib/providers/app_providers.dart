import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:http/http.dart' as http;
import '../core/constants.dart';
import '../core/websocket_client.dart';
import '../models/app_models.dart';

// Backend URL & Navigation State
final backendUrlProvider = StateProvider<String>((ref) => AppConstants.defaultHttpBase);
final wsConnectedProvider = StateProvider<bool>((ref) => false);
final selectedNavigationIndexProvider = StateProvider<int>((ref) => 0);
final isLoadingSnapshotProvider = StateProvider<bool>((ref) => false);
final lastErrorBannerProvider = StateProvider<String?>((ref) => null);

// Core Data Providers
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

// Multi-Desk Workstation Providers
final desksProvider = StateProvider<List<DeskItem>>((ref) => [
  DeskItem(
    deskId: "DESK_MARKET",
    name: "Market Intelligence",
    supervisor: "MarketSupervisor",
    description: "Pair discovery, live price/volume/liquidity tracking, watchlist, and staleness detection.",
    status: "IDLE",
    isPaused: false,
    agents: const ["SCAN"],
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
  ),
  DeskItem(
    deskId: "DESK_WHALE",
    name: "Whale Intelligence",
    supervisor: "WhaleSupervisor",
    description: "Public wallet tracking, on-chain flow classification, and multi-wallet convergence.",
    status: "IDLE",
    isPaused: false,
    agents: const ["WHALE"],
    pollingIntervalSec: 20.0,
    activeTasks: 0,
    queuedTasks: 0,
    completedTasks: 0,
    failedTasks: 0,
    skippedTasks: 0,
    retryCount: 0,
    lastDurationMs: 0.0,
    hasStaleData: false,
    hasMissingData: false,
  ),
  DeskItem(
    deskId: "DESK_INVESTIGATION",
    name: "Token Investigation",
    supervisor: "InvestigationSupervisor",
    description: "Token/pool metadata verification, mint format validation, provider comparison, and risk flags.",
    status: "IDLE",
    isPaused: false,
    agents: const ["VET", "AUDIT"],
    pollingIntervalSec: 25.0,
    activeTasks: 0,
    queuedTasks: 0,
    completedTasks: 0,
    failedTasks: 0,
    skippedTasks: 0,
    retryCount: 0,
    lastDurationMs: 0.0,
    hasStaleData: false,
    hasMissingData: false,
  ),
  DeskItem(
    deskId: "DESK_QUANT",
    name: "Quant Research",
    supervisor: "QuantSupervisor",
    description: "Turnover/volatility indicators, dataset validation, and chronological TRAIN/VAL/TEST backtests.",
    status: "IDLE",
    isPaused: false,
    agents: const ["QUANT"],
    pollingIntervalSec: 30.0,
    activeTasks: 0,
    queuedTasks: 0,
    completedTasks: 0,
    failedTasks: 0,
    skippedTasks: 0,
    retryCount: 0,
    lastDurationMs: 0.0,
    hasStaleData: false,
    hasMissingData: false,
  ),
  DeskItem(
    deskId: "DESK_RISK",
    name: "Risk & Skeptic",
    supervisor: "RiskSupervisor",
    description: "Contrarian anomaly detection, exposure limits, and authoritative backend RISK VETO enforcement.",
    status: "IDLE",
    isPaused: false,
    agents: const ["RISK", "SKEPTIC", "SIZE"],
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
  ),
  DeskItem(
    deskId: "DESK_COMMAND",
    name: "Command Center",
    supervisor: "CHIEF",
    description: "Cross-desk report aggregation, disagreement tracking, provider health, and final consensus.",
    status: "IDLE",
    isPaused: false,
    agents: const ["CHIEF", "AUDIT"],
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
  ),
]);

final deskTasksProvider = StateProvider<List<DeskTaskItem>>((ref) => []);
final deskReportsProvider = StateProvider<List<DeskReportItem>>((ref) => []);
final agentsStatusProvider = StateProvider<List<AgentStatusItem>>((ref) => []);
final watchlistProvider = StateProvider<List<WatchlistItemModel>>((ref) => []);
final systemHealthProvider = StateProvider<Map<String, dynamic>>((ref) => {});
final providersHealthProvider = StateProvider<Map<String, dynamic>>((ref) => {});
final riskAuditProvider = StateProvider<List<Map<String, dynamic>>>((ref) => []);
final strategyBenchmarksProvider = StateProvider<List<Map<String, dynamic>>>((ref) => []);

// Controller Class for Network Actions
class TerminalController {
  final Ref ref;
  WebSocketService? _wsService;
  final Set<String> _seenWsEventIds = <String>{};

  TerminalController(this.ref);

  void initWebSocket() {
    final baseUrl = ref.read(backendUrlProvider);
    final wsBase = baseUrl.replaceFirst("http://", "ws://").replaceFirst("https://", "wss://");
    final wsUrl = "$wsBase/ws/live";

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
    ref.read(isLoadingSnapshotProvider.notifier).state = true;
    try {
      await Future.wait([
        fetchDesks(),
        fetchAllDeskTasksAndReports(),
        fetchAllAgentsStatus(),
        fetchWatchlist(),
        fetchSystemHealth(),
        fetchProvidersHealth(),
        fetchTokens(),
        fetchEvents(),
        fetchWhales(),
        fetchDecisions(),
        fetchPositions(),
        fetchPortfolio(),
        fetchHealth(),
        fetchLearningMetrics(),
        fetchStrategyBenchmarks(),
        fetchRiskAudit(),
        fetchLiveWalletStatus(),
        fetchLiveProposals(),
        fetchLiveTransactions(),
      ]);
      ref.read(lastErrorBannerProvider.notifier).state = null;
    } catch (e) {
      ref.read(lastErrorBannerProvider.notifier).state = "Snapshot sync error: $e";
    } finally {
      ref.read(isLoadingSnapshotProvider.notifier).state = false;
    }
  }

  Future<void> fetchDesks() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/desks"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        if (list.isNotEmpty) {
          ref.read(desksProvider.notifier).state = list.map((e) => DeskItem.fromJson(e)).toList();
        }
      }
    } catch (_) {}
  }

  Future<void> fetchAllDeskTasksAndReports() async {
    try {
      final base = ref.read(backendUrlProvider);
      final desks = ref.read(desksProvider);
      final List<DeskTaskItem> allTasks = [];
      final List<DeskReportItem> allReports = [];
      for (final d in desks) {
        final res = await http.get(Uri.parse("$base/api/desks/${d.deskId}"));
        if (res.statusCode == 200) {
          final Map<String, dynamic> snap = json.decode(res.body);
          final tList = (snap["recent_tasks"] as List<dynamic>?) ?? [];
          final rList = (snap["recent_reports"] as List<dynamic>?) ?? [];
          allTasks.addAll(tList.map((e) => DeskTaskItem.fromJson(e)));
          allReports.addAll(rList.map((e) => DeskReportItem.fromJson(e)));
        }
      }
      allTasks.sort((a, b) => b.startedAt.compareTo(a.startedAt));
      allReports.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      ref.read(deskTasksProvider.notifier).state = allTasks.take(100).toList();
      ref.read(deskReportsProvider.notifier).state = allReports.take(100).toList();
    } catch (_) {}
  }

  Future<void> fetchAllAgentsStatus() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/agents"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(agentsStatusProvider.notifier).state = list.map((e) => AgentStatusItem.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<void> fetchWatchlist() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/watchlist"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(watchlistProvider.notifier).state = list.map((e) => WatchlistItemModel.fromJson(e)).toList();
      }
    } catch (_) {}
  }

  Future<bool> addWatchlistItem(String identifier, String itemType, {String? label, String? notes}) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/watchlist"),
        headers: {"Content-Type": "application/json"},
        body: json.encode({
          "identifier": identifier,
          "item_type": itemType,
          "label": label,
          "notes": notes,
        }),
      );
      if (res.statusCode == 200) {
        await fetchWatchlist();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> removeWatchlistItem(String identifier) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.delete(Uri.parse("$base/api/watchlist/$identifier"));
      if (res.statusCode == 200) {
        await fetchWatchlist();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> pauseDesk(String deskId) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/desks/$deskId/pause"),
        headers: {"X-Admin-Key": "predator-admin-auth-token-2026"},
      );
      if (res.statusCode == 200) {
        await fetchDesks();
        await fetchAllAgentsStatus();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> resumeDesk(String deskId) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/desks/$deskId/resume"),
        headers: {"X-Admin-Key": "predator-admin-auth-token-2026"},
      );
      if (res.statusCode == 200) {
        await fetchDesks();
        await fetchAllAgentsStatus();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> runDeskNow(String deskId, {String? tokenMint}) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/desks/$deskId/run"),
        headers: {"Content-Type": "application/json"},
        body: json.encode({
          "token_mint": tokenMint ?? "So11111111111111111111111111111111111111112",
          "price_usd": 152.40,
          "liquidity_usd": 75000.0,
          "volume_24h_usd": 210000.0,
        }),
      );
      if (res.statusCode == 200) {
        await fetchDesks();
        await fetchAllDeskTasksAndReports();
        await fetchAllAgentsStatus();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<void> fetchSystemHealth() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/system/health"));
      if (res.statusCode == 200) {
        ref.read(systemHealthProvider.notifier).state = json.decode(res.body);
      }
    } catch (_) {}
  }

  Future<void> fetchProvidersHealth() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/market/providers"));
      if (res.statusCode == 200) {
        ref.read(providersHealthProvider.notifier).state = json.decode(res.body);
      }
    } catch (_) {}
  }

  Future<void> fetchRiskAudit() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/live/risk-audit?limit=50"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(riskAuditProvider.notifier).state = list.cast<Map<String, dynamic>>();
      }
    } catch (_) {}
  }

  Future<void> fetchStrategyBenchmarks() async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.get(Uri.parse("$base/api/learning/benchmarks"));
      if (res.statusCode == 200) {
        final List<dynamic> list = json.decode(res.body);
        ref.read(strategyBenchmarksProvider.notifier).state = list.cast<Map<String, dynamic>>();
      }
    } catch (_) {}
  }

  Future<bool> toggleEmergencyKillSwitch(bool active) async {
    try {
      final base = ref.read(backendUrlProvider);
      final res = await http.post(
        Uri.parse("$base/api/live/kill-switch"),
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Key": "predator-admin-auth-token-2026",
        },
        body: json.encode({"active": active}),
      );
      if (res.statusCode == 200) {
        await fetchSystemHealth();
        return true;
      }
    } catch (_) {}
    return false;
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
        await fetchStrategyBenchmarks();
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
    // Event deduplication by event_id
    final evId = data["event_id"]?.toString();
    if (evId != null && evId.isNotEmpty) {
      if (_seenWsEventIds.contains(evId)) return;
      _seenWsEventIds.add(evId);
      if (_seenWsEventIds.length > 500) {
        _seenWsEventIds.remove(_seenWsEventIds.first);
      }
    }

    final evType = data["event_type"]?.toString();
    final payload = (data["payload"] as Map<String, dynamic>?) ?? {};

    if (evType == "desk.status") {
      final updated = DeskItem.fromJson(payload);
      final current = ref.read(desksProvider);
      ref.read(desksProvider.notifier).state = [
        for (final d in current) d.deskId == updated.deskId ? updated : d
      ];
      return;
    }

    if (evType == "agent.task.completed" || evType == "agent.task.failed") {
      final task = DeskTaskItem.fromJson(payload);
      final current = ref.read(deskTasksProvider);
      ref.read(deskTasksProvider.notifier).state = [task, ...current.where((t) => t.taskId != task.taskId).take(99)];
      return;
    }

    if (evType == "agent.report.created") {
      final report = DeskReportItem.fromJson(payload);
      final current = ref.read(deskReportsProvider);
      ref.read(deskReportsProvider.notifier).state = [report, ...current.where((r) => r.reportId != report.reportId).take(99)];
      return;
    }

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
        ref.read(eventsProvider.notifier).state = [newEvent, ...current.where((e) => e.eventId != newEvent.eventId).take(49)];
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
