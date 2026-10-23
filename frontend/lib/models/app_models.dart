class TokenItem {
  final String mint;
  final String? name;
  final String? symbol;
  final double firstObservedTimestamp;
  final double? poolCreatedTimestamp;
  final double? initialLiquidityUsd;
  final String currentLifecycleState;

  TokenItem({
    required this.mint,
    this.name,
    this.symbol,
    required this.firstObservedTimestamp,
    this.poolCreatedTimestamp,
    this.initialLiquidityUsd,
    required this.currentLifecycleState,
  });

  factory TokenItem.fromJson(Map<String, dynamic> json) {
    return TokenItem(
      mint: json['mint'] ?? '',
      name: json['name'],
      symbol: json['symbol'],
      firstObservedTimestamp: (json['first_observed_timestamp'] as num?)?.toDouble() ?? 0.0,
      poolCreatedTimestamp: (json['pool_created_timestamp'] as num?)?.toDouble(),
      initialLiquidityUsd: (json['initial_liquidity_usd'] as num?)?.toDouble(),
      currentLifecycleState: json['current_lifecycle_state'] ?? 'DISCOVERED',
    );
  }
}

class NormalizedEventItem {
  final String eventId;
  final String source;
  final String tokenMint;
  final double? priceUsd;
  final double? liquidityUsd;
  final double? volume24hUsd;
  final String quality;
  final double freshnessSeconds;
  final double localReceiveTimestamp;

  NormalizedEventItem({
    required this.eventId,
    required this.source,
    required this.tokenMint,
    this.priceUsd,
    this.liquidityUsd,
    this.volume24hUsd,
    required this.quality,
    required this.freshnessSeconds,
    required this.localReceiveTimestamp,
  });

  factory NormalizedEventItem.fromJson(Map<String, dynamic> json) {
    return NormalizedEventItem(
      eventId: json['event_id'] ?? '',
      source: json['source'] ?? '',
      tokenMint: json['token_mint'] ?? '',
      priceUsd: (json['price_usd'] as num?)?.toDouble(),
      liquidityUsd: (json['liquidity_usd'] as num?)?.toDouble(),
      volume24hUsd: (json['volume_24h_usd'] as num?)?.toDouble(),
      quality: json['quality'] ?? 'ACCEPTABLE',
      freshnessSeconds: (json['freshness_seconds'] as num?)?.toDouble() ?? 0.0,
      localReceiveTimestamp: (json['local_receive_timestamp'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class WhaleActivityItem {
  final String activityId;
  final String signature;
  final String walletAddress;
  final String tokenMint;
  final String activityType;
  final double? amountUsd;
  final double timestamp;
  final double confidence;

  WhaleActivityItem({
    required this.activityId,
    required this.signature,
    required this.walletAddress,
    required this.tokenMint,
    required this.activityType,
    this.amountUsd,
    required this.timestamp,
    required this.confidence,
  });

  factory WhaleActivityItem.fromJson(Map<String, dynamic> json) {
    return WhaleActivityItem(
      activityId: json['activity_id'] ?? '',
      signature: json['signature'] ?? '',
      walletAddress: json['wallet_address'] ?? '',
      tokenMint: json['token_mint'] ?? '',
      activityType: json['activity_type'] ?? 'UNKNOWN_AMBIGUOUS',
      amountUsd: (json['amount_usd'] as num?)?.toDouble(),
      timestamp: (json['timestamp'] as num?)?.toDouble() ?? 0.0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
    );
  }
}

class AgentDecisionItem {
  final String consensusId;
  final String tokenMint;
  final double timestamp;
  final String agentName;
  final String decision;
  final double? score;
  final double confidence;
  final double latencyMs;
  final List<String> reasonCodes;

  AgentDecisionItem({
    required this.consensusId,
    required this.tokenMint,
    required this.timestamp,
    required this.agentName,
    required this.decision,
    this.score,
    required this.confidence,
    required this.latencyMs,
    required this.reasonCodes,
  });

  factory AgentDecisionItem.fromJson(Map<String, dynamic> json) {
    return AgentDecisionItem(
      consensusId: json['consensus_id'] ?? '',
      tokenMint: json['token_mint'] ?? '',
      timestamp: (json['timestamp'] as num?)?.toDouble() ?? 0.0,
      agentName: json['agent_name'] ?? 'CHIEF',
      decision: json['decision'] ?? 'PASS',
      score: (json['score'] as num?)?.toDouble(),
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      latencyMs: (json['latency_ms'] as num?)?.toDouble() ?? 0.0,
      reasonCodes: (json['reason_codes'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
    );
  }
}

class PositionItem {
  final String positionId;
  final String tokenMint;
  final String tokenSymbol;
  final double qty;
  final double averageEntryPriceUsd;
  final double currentPriceUsd;
  final double investedCapitalUsd;
  final double currentValueUsd;
  final double unrealizedPnlUsd;
  final double unrealizedPnlPct;
  final double realizedPnlUsd;
  final double totalFeesPaidUsd;
  final bool isOpen;
  final bool isStalePrice;
  final double openedAt;
  final String? exitReason;

  PositionItem({
    required this.positionId,
    required this.tokenMint,
    required this.tokenSymbol,
    required this.qty,
    required this.averageEntryPriceUsd,
    required this.currentPriceUsd,
    required this.investedCapitalUsd,
    required this.currentValueUsd,
    required this.unrealizedPnlUsd,
    required this.unrealizedPnlPct,
    required this.realizedPnlUsd,
    required this.totalFeesPaidUsd,
    required this.isOpen,
    required this.isStalePrice,
    required this.openedAt,
    this.exitReason,
  });

  factory PositionItem.fromJson(Map<String, dynamic> json) {
    return PositionItem(
      positionId: json['position_id'] ?? '',
      tokenMint: json['token_mint'] ?? '',
      tokenSymbol: json['token_symbol'] ?? 'TOKEN',
      qty: (json['qty'] as num?)?.toDouble() ?? 0.0,
      averageEntryPriceUsd: (json['average_entry_price_usd'] as num?)?.toDouble() ?? 0.0,
      currentPriceUsd: (json['current_price_usd'] as num?)?.toDouble() ?? 0.0,
      investedCapitalUsd: (json['invested_capital_usd'] as num?)?.toDouble() ?? 0.0,
      currentValueUsd: (json['current_value_usd'] as num?)?.toDouble() ?? 0.0,
      unrealizedPnlUsd: (json['unrealized_pnl_usd'] as num?)?.toDouble() ?? 0.0,
      unrealizedPnlPct: (json['unrealized_pnl_pct'] as num?)?.toDouble() ?? 0.0,
      realizedPnlUsd: (json['realized_pnl_usd'] as num?)?.toDouble() ?? 0.0,
      totalFeesPaidUsd: (json['total_fees_paid_usd'] as num?)?.toDouble() ?? 0.0,
      isOpen: json['is_open'] == 1 || json['is_open'] == true,
      isStalePrice: json['is_stale_price'] == 1 || json['is_stale_price'] == true,
      openedAt: (json['opened_at'] as num?)?.toDouble() ?? 0.0,
      exitReason: json['exit_reason'],
    );
  }
}

class PortfolioSnapshotItem {
  final double cashBalanceUsd;
  final double positionsValueUsd;
  final double totalEquityUsd;
  final double totalRealizedPnlUsd;
  final double totalUnrealizedPnlUsd;
  final double totalFeesPaidUsd;
  final double peakEquityUsd;
  final double currentDrawdownPct;
  final double maxDrawdownPct;
  final int openPositionsCount;

  PortfolioSnapshotItem({
    required this.cashBalanceUsd,
    required this.positionsValueUsd,
    required this.totalEquityUsd,
    required this.totalRealizedPnlUsd,
    required this.totalUnrealizedPnlUsd,
    required this.totalFeesPaidUsd,
    required this.peakEquityUsd,
    required this.currentDrawdownPct,
    required this.maxDrawdownPct,
    required this.openPositionsCount,
  });

  factory PortfolioSnapshotItem.fromJson(Map<String, dynamic> json) {
    return PortfolioSnapshotItem(
      cashBalanceUsd: (json['cash_balance_usd'] as num?)?.toDouble() ?? 10000.0,
      positionsValueUsd: (json['positions_value_usd'] as num?)?.toDouble() ?? 0.0,
      totalEquityUsd: (json['total_equity_usd'] as num?)?.toDouble() ?? 10000.0,
      totalRealizedPnlUsd: (json['total_realized_pnl_usd'] as num?)?.toDouble() ?? 0.0,
      totalUnrealizedPnlUsd: (json['total_unrealized_pnl_usd'] as num?)?.toDouble() ?? 0.0,
      totalFeesPaidUsd: (json['total_fees_paid_usd'] as num?)?.toDouble() ?? 0.0,
      peakEquityUsd: (json['peak_equity_usd'] as num?)?.toDouble() ?? 10000.0,
      currentDrawdownPct: (json['current_drawdown_pct'] as num?)?.toDouble() ?? 0.0,
      maxDrawdownPct: (json['max_drawdown_pct'] as num?)?.toDouble() ?? 0.0,
      openPositionsCount: (json['open_positions_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class DeskItem {
  final String deskId;
  final String name;
  final String supervisor;
  final String description;
  final String status;
  final bool isPaused;
  final List<String> agents;
  final double pollingIntervalSec;
  final int activeTasks;
  final int queuedTasks;
  final int completedTasks;
  final int failedTasks;
  final int skippedTasks;
  final int retryCount;
  final double? lastExecutionAt;
  final double lastDurationMs;
  final String? lastSource;
  final bool hasStaleData;
  final bool hasMissingData;
  final String? lastErrorCode;
  final String? lastErrorMessage;

  DeskItem({
    required this.deskId,
    required this.name,
    required this.supervisor,
    required this.description,
    required this.status,
    required this.isPaused,
    required this.agents,
    required this.pollingIntervalSec,
    required this.activeTasks,
    required this.queuedTasks,
    required this.completedTasks,
    required this.failedTasks,
    required this.skippedTasks,
    required this.retryCount,
    this.lastExecutionAt,
    required this.lastDurationMs,
    this.lastSource,
    required this.hasStaleData,
    required this.hasMissingData,
    this.lastErrorCode,
    this.lastErrorMessage,
  });

  factory DeskItem.fromJson(Map<String, dynamic> json) {
    return DeskItem(
      deskId: json['desk_id'] ?? '',
      name: json['name'] ?? '',
      supervisor: json['supervisor'] ?? '',
      description: json['description'] ?? '',
      status: json['status'] ?? 'IDLE',
      isPaused: json['is_paused'] == 1 || json['is_paused'] == true,
      agents: (json['agents'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      pollingIntervalSec: (json['polling_interval_sec'] as num?)?.toDouble() ?? 15.0,
      activeTasks: (json['active_tasks'] as num?)?.toInt() ?? 0,
      queuedTasks: (json['queued_tasks'] as num?)?.toInt() ?? 0,
      completedTasks: (json['completed_tasks'] as num?)?.toInt() ?? 0,
      failedTasks: (json['failed_tasks'] as num?)?.toInt() ?? 0,
      skippedTasks: (json['skipped_tasks'] as num?)?.toInt() ?? 0,
      retryCount: (json['retry_count'] as num?)?.toInt() ?? 0,
      lastExecutionAt: (json['last_execution_at'] as num?)?.toDouble(),
      lastDurationMs: (json['last_duration_ms'] as num?)?.toDouble() ?? 0.0,
      lastSource: json['last_source'],
      hasStaleData: json['has_stale_data'] == 1 || json['has_stale_data'] == true,
      hasMissingData: json['has_missing_data'] == 1 || json['has_missing_data'] == true,
      lastErrorCode: json['last_error_code'],
      lastErrorMessage: json['last_error_message'],
    );
  }
}

class DeskTaskItem {
  final String taskId;
  final String eventId;
  final String deskId;
  final String agentId;
  final double startedAt;
  final double? finishedAt;
  final double durationMs;
  final String status;
  final String source;
  final double? sourceTimestamp;
  final String observationQuality;
  final String inputSummary;
  final String outputSummary;
  final List<String> missingFields;
  final String? errorCode;
  final String? errorMessageSanitized;
  final double? confidence;
  final String? promptVersion;
  final String? modelId;

  DeskTaskItem({
    required this.taskId,
    required this.eventId,
    required this.deskId,
    required this.agentId,
    required this.startedAt,
    this.finishedAt,
    required this.durationMs,
    required this.status,
    required this.source,
    this.sourceTimestamp,
    required this.observationQuality,
    required this.inputSummary,
    required this.outputSummary,
    required this.missingFields,
    this.errorCode,
    this.errorMessageSanitized,
    this.confidence,
    this.promptVersion,
    this.modelId,
  });

  factory DeskTaskItem.fromJson(Map<String, dynamic> json) {
    return DeskTaskItem(
      taskId: json['task_id'] ?? '',
      eventId: json['event_id'] ?? '',
      deskId: json['desk_id'] ?? '',
      agentId: json['agent_id'] ?? '',
      startedAt: (json['started_at'] as num?)?.toDouble() ?? 0.0,
      finishedAt: (json['finished_at'] as num?)?.toDouble(),
      durationMs: (json['duration_ms'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] ?? 'COMPLETED',
      source: json['source'] ?? 'INTERNAL',
      sourceTimestamp: (json['source_timestamp'] as num?)?.toDouble(),
      observationQuality: json['observation_quality'] ?? 'ACCEPTABLE',
      inputSummary: json['input_summary'] ?? '',
      outputSummary: json['output_summary'] ?? '',
      missingFields: (json['missing_fields'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      errorCode: json['error_code'],
      errorMessageSanitized: json['error_message_sanitized'],
      confidence: (json['confidence'] as num?)?.toDouble(),
      promptVersion: json['prompt_version'],
      modelId: json['model_id'],
    );
  }
}

class DeskReportItem {
  final String reportId;
  final String deskId;
  final String supervisor;
  final String agentId;
  final String? tokenMint;
  final String eventId;
  final String taskId;
  final double observedAt;
  final double? sourceTimestamp;
  final double createdAt;
  final String source;
  final String observationQuality;
  final List<String> observedFacts;
  final List<String> inferredConclusions;
  final List<String> unknownOrMissing;
  final List<String> contradictions;
  final List<String> riskFlags;
  final String decision;
  final double? confidence;
  final String rationale;
  final bool isStale;
  final bool isVeto;
  final Map<String, dynamic> metadata;

  DeskReportItem({
    required this.reportId,
    required this.deskId,
    required this.supervisor,
    required this.agentId,
    this.tokenMint,
    required this.eventId,
    required this.taskId,
    required this.observedAt,
    this.sourceTimestamp,
    required this.createdAt,
    required this.source,
    required this.observationQuality,
    required this.observedFacts,
    required this.inferredConclusions,
    required this.unknownOrMissing,
    required this.contradictions,
    required this.riskFlags,
    required this.decision,
    this.confidence,
    required this.rationale,
    required this.isStale,
    required this.isVeto,
    required this.metadata,
  });

  factory DeskReportItem.fromJson(Map<String, dynamic> json) {
    return DeskReportItem(
      reportId: json['report_id'] ?? '',
      deskId: json['desk_id'] ?? '',
      supervisor: json['supervisor'] ?? '',
      agentId: json['agent_id'] ?? '',
      tokenMint: json['token_mint'],
      eventId: json['event_id'] ?? '',
      taskId: json['task_id'] ?? '',
      observedAt: (json['observed_at'] as num?)?.toDouble() ?? 0.0,
      sourceTimestamp: (json['source_timestamp'] as num?)?.toDouble(),
      createdAt: (json['created_at'] as num?)?.toDouble() ?? 0.0,
      source: json['source'] ?? 'INTERNAL',
      observationQuality: json['observation_quality'] ?? 'ACCEPTABLE',
      observedFacts: (json['observed_facts'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      inferredConclusions: (json['inferred_conclusions'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      unknownOrMissing: (json['unknown_or_missing'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      contradictions: (json['contradictions'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      riskFlags: (json['risk_flags'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      decision: json['decision'] ?? 'PASS',
      confidence: (json['confidence'] as num?)?.toDouble(),
      rationale: json['rationale'] ?? '',
      isStale: json['is_stale'] == 1 || json['is_stale'] == true,
      isVeto: json['is_veto'] == 1 || json['is_veto'] == true,
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? {},
    );
  }
}

class AgentStatusItem {
  final String agentId;
  final String deskId;
  final String status;
  final int activeTasks;
  final int completedTasks;
  final int failedTasks;
  final double? lastExecutionAt;
  final double lastDurationMs;
  final String? lastDecision;
  final double? lastConfidence;
  final int modelUsageCount;
  final String? lastError;

  AgentStatusItem({
    required this.agentId,
    required this.deskId,
    required this.status,
    required this.activeTasks,
    required this.completedTasks,
    required this.failedTasks,
    this.lastExecutionAt,
    required this.lastDurationMs,
    this.lastDecision,
    this.lastConfidence,
    required this.modelUsageCount,
    this.lastError,
  });

  factory AgentStatusItem.fromJson(Map<String, dynamic> json) {
    return AgentStatusItem(
      agentId: json['agent_id'] ?? '',
      deskId: json['desk_id'] ?? '',
      status: json['status'] ?? 'IDLE',
      activeTasks: (json['active_tasks'] as num?)?.toInt() ?? 0,
      completedTasks: (json['completed_tasks'] as num?)?.toInt() ?? 0,
      failedTasks: (json['failed_tasks'] as num?)?.toInt() ?? 0,
      lastExecutionAt: (json['last_execution_at'] as num?)?.toDouble(),
      lastDurationMs: (json['last_duration_ms'] as num?)?.toDouble() ?? 0.0,
      lastDecision: json['last_decision'],
      lastConfidence: (json['last_confidence'] as num?)?.toDouble(),
      modelUsageCount: (json['model_usage_count'] as num?)?.toInt() ?? 0,
      lastError: json['last_error'],
    );
  }
}

class WatchlistItemModel {
  final String identifier;
  final String itemType;
  final String? label;
  final double addedAt;
  final String? notes;

  WatchlistItemModel({
    required this.identifier,
    required this.itemType,
    this.label,
    required this.addedAt,
    this.notes,
  });

  factory WatchlistItemModel.fromJson(Map<String, dynamic> json) {
    return WatchlistItemModel(
      identifier: json['identifier'] ?? '',
      itemType: json['item_type'] ?? 'TOKEN',
      label: json['label'],
      addedAt: (json['added_at'] as num?)?.toDouble() ?? 0.0,
      notes: json['notes'],
    );
  }
}
