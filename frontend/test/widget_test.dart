import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:solana_predator/main.dart';
import 'package:solana_predator/core/constants.dart';
import 'package:solana_predator/views/banner.dart';
import 'package:solana_predator/views/paper_portfolio_view.dart';
import 'package:solana_predator/views/learning_view.dart';
import 'package:solana_predator/views/live_trading_view.dart';
import 'package:solana_predator/providers/app_providers.dart';
import 'package:solana_predator/models/app_models.dart';

void main() {
  testWidgets('Terminal starts up and displays mandatory safety notice', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: SolanaPredatorApp(),
      ),
    );

    // Verify title and security notice are present
    expect(find.text(AppConstants.appName), findsOneWidget);
    expect(find.text(AppConstants.securityNotice), findsOneWidget);
  });

  testWidgets('Terminal displays live WS status in banner', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          wsConnectedProvider.overrideWith((ref) => true),
          portfolioProvider.overrideWith((ref) => PortfolioSnapshotItem(
            cashBalanceUsd: 10000.0,
            positionsValueUsd: 0.0,
            totalEquityUsd: 10000.0,
            totalRealizedPnlUsd: 0.0,
            totalUnrealizedPnlUsd: 0.0,
            totalFeesPaidUsd: 0.0,
            peakEquityUsd: 10000.0,
            currentDrawdownPct: 0.0,
            maxDrawdownPct: 0.0,
            openPositionsCount: 0,
          )),
        ],
        child: const MaterialApp(
          home: Scaffold(body: TerminalSecurityBanner()),
        ),
      ),
    );

    expect(find.text("LIVE WS"), findsOneWidget);
    expect(find.text("EQUITY: \$10000.00"), findsOneWidget);
  });

  testWidgets('Paper Portfolio view displays virtual equity and metrics', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          portfolioProvider.overrideWith((ref) => PortfolioSnapshotItem(
            cashBalanceUsd: 9500.0,
            positionsValueUsd: 600.0,
            totalEquityUsd: 10100.0,
            totalRealizedPnlUsd: 100.0,
            totalUnrealizedPnlUsd: 100.0,
            totalFeesPaidUsd: 5.0,
            peakEquityUsd: 10100.0,
            currentDrawdownPct: 0.0,
            maxDrawdownPct: 0.0,
            openPositionsCount: 1,
          )),
        ],
        child: const MaterialApp(
          home: Scaffold(body: PaperPortfolioView()),
        ),
      ),
    );

    expect(find.text("PAPER PORTFOLIO — DETERMINISTIC SIMULATOR"), findsOneWidget);
    expect(find.text("TOTAL EQUITY"), findsOneWidget);
    expect(find.text("\$10100.00"), findsOneWidget);
    expect(find.text("CASH BALANCE"), findsOneWidget);
    expect(find.text("\$9500.00"), findsOneWidget);
  });

  testWidgets('Learning View displays temporal metrics and strategy benchmarks', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          learningMetricsProvider.overrideWith((ref) => {
            'total_decisions_evaluated': 42,
            'correct_decisions_rate': 0.642,
            'false_positive_rate': 0.143,
            'simulated_net_return_pct': 18.5,
            'max_simulated_drawdown_pct': 4.2,
            'mean_absolute_error_price': 0.0012,
            'results_by_agent': {
              'QUANT': {'evaluated': 10, 'accuracy_rate_pct': 78.0},
              'VET': {'evaluated': 10, 'accuracy_rate_pct': 85.0},
            },
          }),
        ],
        child: const MaterialApp(
          home: Scaffold(body: LearningView()),
        ),
      ),
    );

    expect(find.text("MEASURABLE LEARNING ENGINE"), findsOneWidget);
    expect(find.text("64.2%"), findsOneWidget);
    expect(find.text("Evaluated Decisions"), findsOneWidget);
  });

  testWidgets('Live Trading View displays wallet connection and safety protocols', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          liveWalletProvider.overrideWith((ref) => null),
        ],
        child: const MaterialApp(
          home: Scaffold(body: LiveTradingView()),
        ),
      ),
    );

    expect(find.text("LIVE TRADING MODULE — EXPLICIT USER AUTHORIZATION REQUIRED"), findsOneWidget);
    expect(find.text("Connect Wallet"), findsOneWidget);
  });
}
