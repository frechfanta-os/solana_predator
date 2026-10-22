import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  bool _isConnected = false;
  bool _isManuallyDisconnected = false;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  String _currentWsUrl;

  final void Function(Map<String, dynamic> data) onMessageReceived;
  final void Function(bool connected) onConnectionChanged;

  WebSocketService({
    required String wsUrl,
    required this.onMessageReceived,
    required this.onConnectionChanged,
  }) : _currentWsUrl = wsUrl;

  bool get isConnected => _isConnected;

  void updateUrl(String newUrl) {
    _currentWsUrl = newUrl;
    disconnect();
    connect();
  }

  void connect() {
    if (_isConnected) return;
    _isManuallyDisconnected = false;

    try {
      final uri = Uri.parse(_currentWsUrl);
      _channel = WebSocketChannel.connect(uri);
      _isConnected = true;
      onConnectionChanged(true);

      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(const Duration(seconds: 15), (t) {
        if (_isConnected && _channel != null) {
          try {
            _channel!.sink.add('ping');
          } catch (_) {}
        }
      });

      _channel!.stream.listen(
        (message) {
          try {
            final decoded = json.decode(message.toString());
            if (decoded is Map<String, dynamic>) {
              onMessageReceived(decoded);
            }
          } catch (e) {
            debugPrint("WS parse error: $e");
          }
        },
        onDone: () {
          _handleDisconnect();
        },
        onError: (err) {
          debugPrint("WS error: $err");
          _handleDisconnect();
        },
        cancelOnError: true,
      );
    } catch (e) {
      debugPrint("WS connect error: $e");
      _handleDisconnect();
    }
  }

  void _handleDisconnect() {
    if (_isManuallyDisconnected) return;
    _isConnected = false;
    onConnectionChanged(false);
    _pingTimer?.cancel();
    _channel = null;

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      if (!_isManuallyDisconnected) {
        connect();
      }
    });
  }

  void disconnect() {
    _isManuallyDisconnected = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _pingTimer?.cancel();
    _pingTimer = null;
    _isConnected = false;
    _channel?.sink.close();
    _channel = null;
    onConnectionChanged(false);
  }
}
