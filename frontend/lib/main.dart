import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme.dart';
import 'core/constants.dart';
import 'providers/app_providers.dart';
import 'views/banner.dart';
import 'views/market_overview_view.dart';
import 'views/token_radar_view.dart';
import 'views/whale_activity_view.dart';
import 'views/agent_decisions_view.dart';
import 'views/paper_portfolio_view.dart';
import 'views/positions_view.dart';
import 'views/exit_analysis_view.dart';
import 'views/event_log_view.dart';
import 'views/latency_health_view.dart';
import 'views/config_risk_view.dart';
import 'views/learning_view.dart';
import 'views/live_trading_view.dart';

void main() {
  runApp(
    const ProviderScope(
      child: SolanaPredatorApp(),
    ),
  );
}

class SolanaPredatorApp extends StatelessWidget {
  const SolanaPredatorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConstants.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const TerminalMainScreen(),
    );
  }
}

class TerminalMainScreen extends ConsumerStatefulWidget {
  const TerminalMainScreen({super.key});

  @override
  ConsumerState<TerminalMainScreen> createState() => _TerminalMainScreenState();
}

class _TerminalMainScreenState extends ConsumerState<TerminalMainScreen> {
  int _selectedIndex = 0;
  late final TerminalController _controller;

  final List<Widget> _views = const [
    MarketOverviewView(),
    TokenRadarView(),
    WhaleActivityView(),
    AgentDecisionsView(),
    LearningView(),
    LiveTradingView(),
    PaperPortfolioView(),
    PositionsView(),
    ExitAnalysisView(),
    EventLogView(),
    LatencyHealthView(),
    ConfigRiskView(),
  ];

  @override
  void initState() {
    super.initState();
    _controller = ref.read(terminalControllerProvider);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _controller.initWebSocket();
      _controller.refreshAll();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth >= 900;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.bolt, color: AppTheme.predatorGreen),
            const SizedBox(width: 8),
            const Text(AppConstants.appName),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: AppTheme.cardBg,
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text("v1.0.0", style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: "Refresh Data",
            onPressed: () => ref.read(terminalControllerProvider).refreshAll(),
          ),
        ],
      ),
      body: Column(
        children: [
          const TerminalSecurityBanner(),
          Expanded(
            child: isDesktop
                ? Row(
                    children: [
                      NavigationRail(
                        selectedIndex: _selectedIndex,
                        onDestinationSelected: (idx) => setState(() => _selectedIndex = idx),
                        backgroundColor: AppTheme.surfaceBg,
                        labelType: NavigationRailLabelType.all,
                        selectedIconTheme: const IconThemeData(color: AppTheme.predatorGreen),
                        unselectedIconTheme: const IconThemeData(color: AppTheme.textMuted),
                        selectedLabelTextStyle: const TextStyle(color: AppTheme.predatorGreen, fontSize: 11, fontWeight: FontWeight.bold),
                        unselectedLabelTextStyle: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
                        destinations: const [
                          NavigationRailDestination(icon: Icon(Icons.show_chart), label: Text("Market")),
                          NavigationRailDestination(icon: Icon(Icons.radar), label: Text("Radar")),
                          NavigationRailDestination(icon: Icon(Icons.waves), label: Text("Whales")),
                          NavigationRailDestination(icon: Icon(Icons.psychology), label: Text("Agents")),
                          NavigationRailDestination(icon: Icon(Icons.school), label: Text("Learning")),
                          NavigationRailDestination(icon: Icon(Icons.bolt), label: Text("Live Trade")),
                          NavigationRailDestination(icon: Icon(Icons.account_balance), label: Text("Portfolio")),
                          NavigationRailDestination(icon: Icon(Icons.view_list), label: Text("Positions")),
                          NavigationRailDestination(icon: Icon(Icons.logout), label: Text("Exits")),
                          NavigationRailDestination(icon: Icon(Icons.terminal), label: Text("Events")),
                          NavigationRailDestination(icon: Icon(Icons.speed), label: Text("Health")),
                          NavigationRailDestination(icon: Icon(Icons.tune), label: Text("Config")),
                        ],
                      ),
                      const VerticalDivider(width: 1),
                      Expanded(child: _views[_selectedIndex]),
                    ],
                  )
                : _views[_selectedIndex],
          ),
        ],
      ),
      bottomNavigationBar: !isDesktop
          ? BottomNavigationBar(
              currentIndex: _selectedIndex > 4 ? 0 : _selectedIndex,
              onTap: (idx) => setState(() => _selectedIndex = idx),
              backgroundColor: AppTheme.surfaceBg,
              selectedItemColor: AppTheme.predatorGreen,
              unselectedItemColor: AppTheme.textMuted,
              type: BottomNavigationBarType.fixed,
              selectedFontSize: 10,
              unselectedFontSize: 9,
              items: const [
                BottomNavigationBarItem(icon: Icon(Icons.show_chart), label: "Market"),
                BottomNavigationBarItem(icon: Icon(Icons.radar), label: "Radar"),
                BottomNavigationBarItem(icon: Icon(Icons.waves), label: "Whales"),
                BottomNavigationBarItem(icon: Icon(Icons.account_balance), label: "Paper"),
                BottomNavigationBarItem(icon: Icon(Icons.tune), label: "Config"),
              ],
            )
          : null,
    );
  }
}
