import { useEffect, useRef } from "react";

const WS_BASE_URL = "ws://127.0.0.1:8000";

/**
 * Subscribes to live updates for a given auction. Calls onUpdate(payload)
 * whenever the backend broadcasts a change (new bid, retraction, closure).
 * Automatically reconnects if the connection drops.
 */
export function useAuctionSocket(auctionId, onUpdate) {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate; // always call the latest callback

  useEffect(() => {
    if (!auctionId) return;

    let socket;
    let reconnectTimer;
    let closedByCleanup = false;

    function connect() {
      socket = new WebSocket(`${WS_BASE_URL}/ws/auctions/${auctionId}`);

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onUpdateRef.current(data);
        } catch {
          // ignore malformed messages
        }
      };

      socket.onclose = () => {
        if (!closedByCleanup) {
          // Reconnect after a short delay (e.g. server restarted, network blip)
          reconnectTimer = setTimeout(connect, 2000);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      closedByCleanup = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [auctionId]);
}
