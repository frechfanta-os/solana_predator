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
