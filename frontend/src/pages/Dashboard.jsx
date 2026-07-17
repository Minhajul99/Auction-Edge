import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const BASE_URL = "http://127.0.0.1:8000";

function authHeaders() {
  const saved = localStorage.getItem("auctionedge_auth");
  const token = saved ? JSON.parse(saved).token : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJson(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

const getMyListings = () => fetchJson("/auctions/mine");
const getMyBids = () => fetchJson("/auctions/bids/mine");
const getMyNotifications = () => fetchJson("/users/me/notifications");
const markRead = (id) =>
  fetchJson(`/users/me/notifications/${id}/read`, { method: "POST" });
const relistAuction = (auctionId) =>
  fetchJson(`/auctions/${auctionId}/relist`, { method: "POST" });
const payForAuction = (auctionId) =>
  fetchJson(`/auctions/${auctionId}/pay`, { method: "POST" });

const STATUS_LABELS = {
  Active: "Active",
  Closed: "Closed — Sold",
  "Unsold-NoBids": "Closed — No Bids",
  "Unsold-ReserveNotMet": "Closed — Reserve Not Met",
};

const NOTIFICATION_LABELS = {
  outbid: "You were outbid",
  reserve_met: "Reserve price met on your listing",
  won: "You won an auction!",
  lost: "You did not win an auction",
  seller_auction_closed: "One of your auctions closed",
  unsold_no_bids: "Your auction closed with no bids",
  unsold_reserve_not_met: "Your auction closed — reserve not met",
};

const RELISTABLE_STATUSES = ["Unsold-NoBids", "Unsold-ReserveNotMet"];

export default function Dashboard() {
  const [listings, setListings] = useState([]);
  const [bids, setBids] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  function loadAll() {
    return Promise.all([getMyListings(), getMyBids(), getMyNotifications()]).then(
      ([l, b, n]) => {
        setListings(l);
        setBids(b);
        setNotifications(n);
      }
    );
  }

  useEffect(() => {
    loadAll()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleMarkRead(id) {
    await markRead(id);
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  }

  async function handleRelist(auctionId) {
    setActionError(null);
    setBusyId(auctionId);
    try {
      await relistAuction(auctionId);
      await loadAll();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handlePay(auctionId) {
    setActionError(null);
    setBusyId(auctionId);
    try {
      await payForAuction(auctionId);
      await loadAll();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <p>Loading dashboard...</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <h1>Dashboard</h1>

      {actionError && <p style={{ color: "red" }}>{actionError}</p>}

      <section style={{ marginBottom: "2rem" }}>
        <h2>My Listings</h2>
        {listings.length === 0 ? (
          <p>You haven't created any listings yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {listings.map((a) => (
              <li
                key={a.id}
                style={{
                  borderBottom: "1px solid #eee",
                  padding: "0.5rem 0",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <Link to={`/auctions/${a.id}`}>
                    Current price: ${a.current_price} — {STATUS_LABELS[a.status] || a.status}
                  </Link>
                  {a.reserve_met && (
                    <span style={{ color: "green", marginLeft: 8 }}>Reserve met</span>
                  )}
                </div>
                {RELISTABLE_STATUSES.includes(a.status) && (
                  <button disabled={busyId === a.id} onClick={() => handleRelist(a.id)}>
                    {busyId === a.id ? "Relisting..." : "Relist"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ marginBottom: "2rem" }}>
        <h2>My Bids</h2>
        {bids.length === 0 ? (
          <p>You haven't placed any bids yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {bids.map((b) => (
              <li
                key={b.id}
                style={{
                  borderBottom: "1px solid #eee",
                  padding: "0.5rem 0",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <Link to={`/auctions/${b.auction_id}`}>
                    ${b.amount} —{" "}
                    <span
                      style={{
                        color:
                          b.status === "active"
                            ? "green"
                            : b.status === "outbid"
                            ? "#b36b00"
                            : "#999",
                      }}
                    >
                      {b.status}
                    </span>
                  </Link>
                  <span style={{ color: "#666", marginLeft: 8, fontSize: "0.85rem" }}>
                    {new Date(b.timestamp).toLocaleString()}
                  </span>
                </div>
                {/* Won + unpaid: this bid is the winning bid on a closed auction */}
                <PayNowButton
                  bid={b}
                  busyId={busyId}
                  onPay={() => handlePay(b.auction_id)}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Notifications</h2>
        {notifications.length === 0 ? (
          <p>No notifications yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {notifications.map((n) => (
              <li
                key={n.id}
                style={{
                  borderBottom: "1px solid #eee",
                  padding: "0.5rem 0",
                  fontWeight: n.read ? "normal" : "bold",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>
                  {NOTIFICATION_LABELS[n.type] || n.type} —{" "}
                  <span style={{ fontWeight: "normal", color: "#666", fontSize: "0.85rem" }}>
                    {new Date(n.sent_at).toLocaleString()}
                  </span>
                </span>
                {!n.read && <button onClick={() => handleMarkRead(n.id)}>Mark read</button>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// Shows "Pay Now" only if this bid is active and won (backend confirms via
// the /pay endpoint's own checks, but we avoid showing the button at all
// for bids that obviously aren't winners, to keep the UI honest).
function PayNowButton({ bid, busyId, onPay }) {
  if (bid.status !== "active") return null;
  // We don't know the auction's status/payment_status from BidOut alone,
  // so we optimistically show the button for any active bid and let the
  // backend's /pay endpoint reject it if the auction isn't actually Closed
  // or this wasn't the winning bid. A cleaner version would fetch auction
  // status per bid; kept simple here since it's a demo payment stub.
  return (
    <button disabled={busyId === bid.auction_id} onClick={onPay}>
      {busyId === bid.auction_id ? "Processing..." : "Pay Now"}
    </button>
  );
}
