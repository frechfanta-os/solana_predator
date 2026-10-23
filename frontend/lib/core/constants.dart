// Global constants and configuration for SOLANA PREDATOR terminal.

class AppConstants {
  static const String appName = "SOLANA PREDATOR";
  static const String appVersion = "2.0.0";
  static const String securityNotice = "LIVE MARKET DATA — PAPER TRADING ONLY";

  // Default backend endpoints (Configurable at runtime)
  static const String defaultHttpBase = "http://127.0.0.1:8000";
  static const String defaultWsBase = "ws://127.0.0.1:8000/ws/live";

  // 10 Multi-Desk Workstation Navigation Destinations
  static const List<String> navigationTabs = [
    "Command Center",
    "Market Intelligence",
    "Whale Intelligence",
    "Token Investigation",
    "Quant Research",
    "Risk & Skeptic",
    "Paper Portfolio",
    "Agent Activity",
    "Data Sources",
    "Settings",
  ];
}
