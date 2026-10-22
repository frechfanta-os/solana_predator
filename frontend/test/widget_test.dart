import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:solana_predator/main.dart';
import 'package:solana_predator/core/constants.dart';
import 'package:solana_predator/views/banner.dart';
import 'package:solana_predator/views/paper_portfolio_view.dart';
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
}
