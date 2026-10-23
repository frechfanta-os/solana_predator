import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme.dart';
import 'core/constants.dart';
import 'providers/app_providers.dart';
import 'views/banner.dart';
import 'views/command_center_view.dart';
import 'views/market_overview_view.dart';
import 'views/whale_activity_view.dart';
import 'views/token_investigation_view.dart';
import 'views/learning_view.dart';
import 'views/risk_skeptic_view.dart';
import 'views/paper_portfolio_view.dart';
import 'views/agent_decisions_view.dart';
import 'views/data_sources_view.dart';
import 'views/config_risk_view.dart';

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
  late final TerminalController _controller;

  final List<Widget> _views = const [
    CommandCenterView(),       // 0: Command Center (DESK_COMMAND)
    MarketOverviewView(),      // 1: Market Intelligence (DESK_MARKET)
    WhaleActivityView(),       // 2: Whale Intelligence (DESK_WHALE)
    TokenInvestigationView(),  // 3: Token Investigation (DESK_INVESTIGATION)
    LearningView(),            // 4: Quant Research (DESK_QUANT)
    RiskSkepticView(),         // 5: Risk & Skeptic (DESK_RISK)
    PaperPortfolioView(),      // 6: Paper Portfolio
    AgentDecisionsView(),      // 7: Agent Activity
    DataSourcesView(),         // 8: Data Sources
    ConfigRiskView(),          // 9: Settings
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
    final selectedIndex = ref.watch(selectedNavigationIndexProvider);
    final safeIndex = (selectedIndex >= 0 && selectedIndex < _views.length) ? selectedIndex : 0;

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
              child: const Text(
                "MULTI-DESK v2.0",
                style: TextStyle(fontSize: 10, color: AppTheme.solanaCyan, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: "Refresh Workstation Telemetry",
            onPressed: () => ref.read(terminalControllerProvider).refreshAll(),
          ),
        ],
      ),
      drawer: !isDesktop
          ? Drawer(
              backgroundColor: AppTheme.surfaceBg,
              child: SafeArea(
                child: ListView(
                  padding: EdgeInsets.zero,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      color: AppTheme.darkBg,
                      child: const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            "SOLANA PREDATOR",
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.predatorGreen),
                          ),
                          SizedBox(height: 4),
                          Text(
                            "Multi-Desk Intelligence Terminal",
                            style: TextStyle(fontSize: 11, color: AppTheme.textMuted),
                          ),
                        ],
                      ),
                    ),
                    _drawerItem(0, Icons.dashboard_customize, "Command Center", safeIndex),
                    _drawerItem(1, Icons.show_chart, "Market Intelligence", safeIndex),
                    _drawerItem(2, Icons.waves, "Whale Intelligence", safeIndex),
                    _drawerItem(3, Icons.fact_check, "Token Investigation", safeIndex),
                    _drawerItem(4, Icons.functions, "Quant Research", safeIndex),
                    _drawerItem(5, Icons.gpp_maybe, "Risk & Skeptic", safeIndex),
                    const Divider(color: AppTheme.borderCol),
                    _drawerItem(6, Icons.account_balance, "Paper Portfolio", safeIndex),
                    _drawerItem(7, Icons.psychology, "Agent Activity", safeIndex),
                    _drawerItem(8, Icons.dns, "Data Sources", safeIndex),
                    _drawerItem(9, Icons.tune, "Settings", safeIndex),
                  ],
                ),
              ),
            )
          : null,
      body: Column(
        children: [
          const TerminalSecurityBanner(),
          Expanded(
            child: isDesktop
                ? Row(
                    children: [
                      NavigationRail(
                        selectedIndex: safeIndex,
                        onDestinationSelected: (idx) => ref.read(selectedNavigationIndexProvider.notifier).state = idx,
                        backgroundColor: AppTheme.surfaceBg,
                        labelType: NavigationRailLabelType.all,
                        selectedIconTheme: const IconThemeData(color: AppTheme.predatorGreen),
                        unselectedIconTheme: const IconThemeData(color: AppTheme.textMuted),
                        selectedLabelTextStyle: const TextStyle(color: AppTheme.predatorGreen, fontSize: 10, fontWeight: FontWeight.bold),
                        unselectedLabelTextStyle: const TextStyle(color: AppTheme.textMuted, fontSize: 9),
                        destinations: const [
                          NavigationRailDestination(icon: Icon(Icons.dashboard_customize), label: Text("Command Center")),
                          NavigationRailDestination(icon: Icon(Icons.show_chart), label: Text("Market Intel")),
                          NavigationRailDestination(icon: Icon(Icons.waves), label: Text("Whale Intel")),
                          NavigationRailDestination(icon: Icon(Icons.fact_check), label: Text("Investigation")),
                          NavigationRailDestination(icon: Icon(Icons.functions), label: Text("Quant Research")),
                          NavigationRailDestination(icon: Icon(Icons.gpp_maybe), label: Text("Risk & Skeptic")),
                          NavigationRailDestination(icon: Icon(Icons.account_balance), label: Text("Paper Portfolio")),
                          NavigationRailDestination(icon: Icon(Icons.psychology), label: Text("Agent Activity")),
                          NavigationRailDestination(icon: Icon(Icons.dns), label: Text("Data Sources")),
                          NavigationRailDestination(icon: Icon(Icons.tune), label: Text("Settings")),
                        ],
                      ),
                      const VerticalDivider(width: 1),
                      Expanded(child: _views[safeIndex]),
                    ],
                  )
                : _views[safeIndex],
          ),
        ],
      ),
      bottomNavigationBar: !isDesktop
          ? BottomNavigationBar(
              currentIndex: safeIndex > 4 ? 0 : safeIndex,
              onTap: (idx) => ref.read(selectedNavigationIndexProvider.notifier).state = idx,
              backgroundColor: AppTheme.surfaceBg,
              selectedItemColor: AppTheme.predatorGreen,
              unselectedItemColor: AppTheme.textMuted,
              type: BottomNavigationBarType.fixed,
              selectedFontSize: 10,
              unselectedFontSize: 9,
              items: const [
                BottomNavigationBarItem(icon: Icon(Icons.dashboard_customize), label: "Command"),
                BottomNavigationBarItem(icon: Icon(Icons.show_chart), label: "Market"),
                BottomNavigationBarItem(icon: Icon(Icons.waves), label: "Whales"),
                BottomNavigationBarItem(icon: Icon(Icons.fact_check), label: "Investigate"),
                BottomNavigationBarItem(icon: Icon(Icons.functions), label: "Quant"),
              ],
            )
          : null,
    );
  }

  Widget _drawerItem(int index, IconData icon, String title, int currentIndex) {
    final selected = currentIndex == index;
    return ListTile(
      dense: true,
      leading: Icon(icon, size: 18, color: selected ? AppTheme.predatorGreen : AppTheme.textMuted),
      title: Text(
        title,
        style: TextStyle(
          fontSize: 12,
          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
          color: selected ? AppTheme.predatorGreen : AppTheme.textBright,
        ),
      ),
      selected: selected,
      onTap: () {
        Navigator.of(context).pop();
        ref.read(selectedNavigationIndexProvider.notifier).state = index;
      },
    );
  }
}
