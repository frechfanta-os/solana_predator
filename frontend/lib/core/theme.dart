import 'package:flutter/material.dart';

class AppTheme {
  static const Color darkBg = Color(0xFF0D1117);
  static const Color scaffoldBg = darkBg;
  static const Color surfaceBg = Color(0xFF161B22);
  static const Color cardBg = Color(0xFF21262D);
  static const Color borderCol = Color(0xFF30363D);

  static const Color predatorGreen = Color(0xFF00FF66);
  static const Color solanaCyan = Color(0xFF00E5FF);
  static const Color accentCyan = solanaCyan;
  static const Color warningOrange = Color(0xFFFF9900);
  static const Color warningAmber = warningOrange;
  static const Color dangerRed = Color(0xFFFF3366);
  static const Color textMuted = Color(0xFF8B949E);
  static const Color textBright = Color(0xFFF0F6FC);

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: darkBg,
      primaryColor: predatorGreen,
      cardColor: surfaceBg,
      dividerColor: borderCol,
      appBarTheme: const AppBarTheme(
        backgroundColor: surfaceBg,
        elevation: 0,
        titleTextStyle: TextStyle(
          color: textBright,
          fontSize: 18,
          fontWeight: FontWeight.bold,
          letterSpacing: 1.2,
        ),
      ),
      colorScheme: const ColorScheme.dark(
        primary: predatorGreen,
        secondary: solanaCyan,
        surface: surfaceBg,
        error: dangerRed,
      ),
      textTheme: const TextTheme(
        bodyMedium: TextStyle(color: textBright, fontSize: 13),
        bodySmall: TextStyle(color: textMuted, fontSize: 11),
      ),
    );
  }
}
