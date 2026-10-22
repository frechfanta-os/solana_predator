// Global constants and configuration for SOLANA PREDATOR terminal.

class AppConstants {
  static const String appName = "SOLANA PREDATOR";
  static const String appVersion = "1.0.0";
  static const String securityNotice = "LIVE MARKET DATA — PAPER TRADING ONLY";
  
  // Default backend endpoints (Configurable at runtime)
  static const String defaultHttpBase = "http://127.0.0.1:8000";
  static const String defaultWsBase = "ws://127.0.0.1:8000/ws";

  // Navigation Items
  static const List<String> navigationTabs = [
    "Market",
    "Radar",
    "Whales",
    "Agents",
    "Portfolio",
    "Positions",
    "Exit Monitor",
    "Event Log",
    "Health & Latency",
    "Config & Risk",
  ];
}
