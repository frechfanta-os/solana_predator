import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../core/constants.dart';
import '../providers/app_providers.dart';

class TerminalSecurityBanner extends ConsumerWidget {
  const TerminalSecurityBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isWsConnected = ref.watch(wsConnectedProvider);
    final portfolio = ref.watch(portfolioProvider);

    return Container(
      width: double.infinity,
      color: const Color(0xFF1F1A00),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.shield_outlined, color: AppTheme.warningOrange, size: 18),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              AppConstants.securityNotice,
              style: TextStyle(
                color: AppTheme.warningOrange,
                fontSize: 12,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.1,
              ),
            ),
          ),
          if (portfolio != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.surfaceBg,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: AppTheme.borderCol),
              ),
              child: Text(
                "EQUITY: \$${portfolio.totalEquityUsd.toStringAsFixed(2)}",
                style: const TextStyle(
                  color: AppTheme.predatorGreen,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 12),
          ],
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isWsConnected ? AppTheme.predatorGreen : AppTheme.dangerRed,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                isWsConnected ? "LIVE WS" : "DISCONNECTED",
                style: TextStyle(
                  color: isWsConnected ? AppTheme.predatorGreen : AppTheme.dangerRed,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
