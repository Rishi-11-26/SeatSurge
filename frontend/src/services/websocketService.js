/**
 * SeatSurge Real-Time WebSocket Fan-Out Service (Phase 3 Client Layer)
 *
 * Implements protocol specified in docs/api-contract.md §8:
 * - URL: ws://localhost:8000/ws/events?event_id={eventId}
 * - Inbound Message: { type: "SEAT_STATUS_CHANGE", seq: 1043, event_id: 1, updates: [{ seat_id, status, hold_id }], timestamp }
 * - Gap Detection: If seq > lastSeq + 1, triggers RESYNC action and/or full snapshot refresh callback.
 * - Outbound Resync: { action: "RESYNC", from_seq: lastSeq }
 * - Duplicate & Out-of-Order Handling: Drops messages where seq <= lastSeq to guarantee idempotency and monotonic state.
 * - Lifecycle: Exponential backoff reconnection, cleanup on unmount, multi-listener pub/sub.
 *
 * BACKEND COORDINATION STATUS:
 * - Client protocol implementation complete and type-safe.
 * - Live WebSocket server endpoint on backend (Phase 3) is pending merge on backend main branch.
 */

import { WS_BASE_URL } from './api';

export const WS_STATUS = Object.freeze({
  DISCONNECTED: 'DISCONNECTED',
  CONNECTING:   'CONNECTING',
  CONNECTED:    'CONNECTED',
  RECONNECTING: 'RECONNECTING',
  ERROR:        'ERROR',
});

class SeatSurgeWebSocketService {
  constructor() {
    this.ws = null;
    this.status = WS_STATUS.DISCONNECTED;
    this.eventId = null;
    this.lastSeq = 0;
    this.listeners = new Set();
    this.statusListeners = new Set();
    this.gapListeners = new Set();
    this.snapshotListeners = new Set();

    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimer = null;
    this.isExplicitlyClosed = false;
  }

  /**
   * Set connection status and notify all listeners
   */
  _setStatus(newStatus) {
    if (this.status === newStatus) return;
    this.status = newStatus;
    for (const listener of this.statusListeners) {
      try {
        listener(newStatus);
      } catch (err) {
        console.error('[WebSocketService] Error in status listener', err);
      }
    }
  }

  /**
   * Connect to backend WebSocket for a given event
   */
  connect(eventId = 1) {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      if (this.eventId === eventId) return; // Already connected to this event
      this.disconnect();
    }

    this.eventId = eventId;
    this.isExplicitlyClosed = false;
    this._setStatus(this.reconnectAttempts > 0 ? WS_STATUS.RECONNECTING : WS_STATUS.CONNECTING);

    const url = `${WS_BASE_URL}?event_id=${eventId}`;

    try {
      this.ws = new WebSocket(url);
    } catch (err) {
      console.warn('[WebSocketService] WebSocket construction failed:', err);
      this._setStatus(WS_STATUS.ERROR);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.info(`[WebSocketService] Connected to ${url}`);
      this._setStatus(WS_STATUS.CONNECTED);
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      this._handleMessage(event);
    };

    this.ws.onerror = (err) => {
      console.warn('[WebSocketService] Connection error:', err);
      this._setStatus(WS_STATUS.ERROR);
    };

    this.ws.onclose = (event) => {
      console.info(`[WebSocketService] Closed (code=${event.code}, clean=${event.wasClean})`);
      this.ws = null;

      if (!this.isExplicitlyClosed) {
        this._setStatus(WS_STATUS.DISCONNECTED);
        this._scheduleReconnect();
      } else {
        this._setStatus(WS_STATUS.DISCONNECTED);
      }
    };
  }

  /**
   * Inbound message handler with sequence tracking, gap detection & duplicate suppression
   */
  _handleMessage(event) {
    try {
      const data = JSON.parse(event.data);
      if (!data || typeof data !== 'object') return;

      const seq = data.seq;

      // Handle Full Snapshot broadcast response
      if (data.type === 'SNAPSHOT' || data.type === 'SNAPSHOT_RESYNC') {
        if (typeof seq === 'number') {
          this.lastSeq = Math.max(this.lastSeq, seq);
        }
        for (const snapListener of this.snapshotListeners) {
          try {
            snapListener(data);
          } catch (err) {
            console.error('[WebSocketService] Error in snapshot listener', err);
          }
        }
        return;
      }

      // Handle Incremental Status Change
      if (data.type === 'SEAT_STATUS_CHANGE') {
        if (typeof seq === 'number') {
          // 1. Duplicate or out-of-order stale check
          if (this.lastSeq > 0 && seq <= this.lastSeq) {
            console.info(`[WebSocketService] Suppressing duplicate/stale event (seq ${seq} <= lastSeq ${this.lastSeq}).`);
            return; // Ignore stale or duplicate event to guarantee idempotency
          }

          // 2. Sequence gap detection
          if (this.lastSeq > 0 && seq > this.lastSeq + 1) {
            console.warn(`[WebSocketService] Sequence gap detected: expected ${this.lastSeq + 1}, got ${seq}. Requesting resync.`);
            this.sendResync(this.lastSeq);

            // Notify gap listeners to trigger full snapshot refresh
            for (const gapListener of this.gapListeners) {
              try {
                gapListener(this.lastSeq, seq);
              } catch (err) {
                console.error('[WebSocketService] Error in gap listener', err);
              }
            }
          }

          this.lastSeq = seq;
        }

        // Notify seat status update listeners
        const updates = data.updates || [];
        for (const listener of this.listeners) {
          try {
            listener({ updates, seq: data.seq, timestamp: data.timestamp });
          } catch (err) {
            console.error('[WebSocketService] Error in seat update listener', err);
          }
        }
      }
    } catch (err) {
      console.error('[WebSocketService] Failed to parse message JSON:', event.data, err);
    }
  }

  /**
   * Send gap resync action to server per contract §8
   */
  sendResync(fromSeq) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'RESYNC',
        from_seq: fromSeq,
      }));
    }
  }

  /**
   * Schedule exponential backoff reconnection
   */
  _scheduleReconnect() {
    if (this.isExplicitlyClosed) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.info('[WebSocketService] Max reconnect attempts reached. Standing by.');
      this._setStatus(WS_STATUS.DISCONNECTED);
      return;
    }

    const backoffMs = Math.min(15000, 1000 * Math.pow(2, this.reconnectAttempts));
    this.reconnectAttempts++;
    console.info(`[WebSocketService] Reconnecting in ${backoffMs}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.connect(this.eventId);
    }, backoffMs);
  }

  /**
   * Explicitly disconnect and cleanup
   */
  disconnect() {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch { /* ignore */ }
      this.ws = null;
    }
    this._setStatus(WS_STATUS.DISCONNECTED);
  }

  /**
   * Reset sequence number (e.g. on full snapshot refresh)
   */
  resetSeq(seq = 0) {
    this.lastSeq = seq;
  }

  /**
   * Subscribe to seat updates: cb({ updates, seq, timestamp })
   */
  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Subscribe to connection status changes: cb(status)
   */
  onStatusChange(callback) {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  /**
   * Subscribe to sequence gap occurrences: cb(lastSeq, newSeq)
   */
  onGap(callback) {
    this.gapListeners.add(callback);
    return () => this.gapListeners.delete(callback);
  }

  /**
   * Subscribe to full snapshot payloads received over WebSocket
   */
  onSnapshot(callback) {
    this.snapshotListeners.add(callback);
    return () => this.snapshotListeners.delete(callback);
  }

  /**
   * Inspect current connection state
   */
  getStatus() {
    return {
      status: this.status,
      eventId: this.eventId,
      lastSeq: this.lastSeq,
      reconnectAttempts: this.reconnectAttempts,
      url: `${WS_BASE_URL}?event_id=${this.eventId || 1}`,
    };
  }
}

// Export singleton instance
export const websocketService = new SeatSurgeWebSocketService();
export default websocketService;
