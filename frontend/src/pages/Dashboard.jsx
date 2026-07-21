import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BASE_URL, extractErrorDetail } from "../services/api";
import { useToast } from "../components/Toast";
import PaymentModal from "../components/PaymentModal";

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
    throw new Error(extractErrorDetail(body, res.statusText));
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
const cancelAuction = (auctionId) =>
  fetchJson(`/auctions/${auctionId}/cancel`, { method: "POST" });

const STATUS_LABELS = {
  Active: "Active",
  Closed: "Closed — Sold",
  "Unsold-NoBids": "Closed — No Bids",
  "Unsold-ReserveNotMet": "Closed — Reserve Not Met",
  Cancelled: "Cancelled",
};

const STATUS_BADGE_CLASSES = {
  Active: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  Closed: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  "Unsold-NoBids": "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  "Unsold-ReserveNotMet": "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  Cancelled: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
};

const BID_STATUS_CLASSES = {
  active: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  outbid: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  withdrawn: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400",
};

const NOTIFICATION_LABELS = {
  outbid: "You were outbid",
  reserve_met: "Reserve price met on your listing",
  won: "You won an auction!",
  lost: "You did not win an auction",
  seller_auction_closed: "One of your auctions closed",
  unsold_no_bids: "Your auction closed with no bids",
  unsold_reserve_not_met: "Your auction closed — reserve not met",
  auction_cancelled: "An auction you bid on was cancelled by the seller",
};

const RELISTABLE_STATUSES = ["Unsold-NoBids", "Unsold-ReserveNotMet"];

function Badge({ children, className }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${className}`}>
      {children}
    </span>
  );
}

function SecondaryButton({ children, ...props }) {
  return (
    <button
      {...props}
      className="shrink-0 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/15 dark:text-gray-200 dark:hover:bg-white/10"
    >
      {children}
    </button>
  );
}

function Section({ title, children }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-gray-900">
      <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
      {children}
    </section>
  );
}

function EmptyRow({ children }) {
  return <p className="py-2 text-sm text-gray-500 dark:text-gray-400">{children}</p>;
}

export default function Dashboard() {
  const { showToast } = useToast();
  const [listings, setListings] = useState([]);
  const [bids, setBids] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [payingBid, setPayingBid] = useState(null);

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
    await payForAuction(auctionId);
    await loadAll();
    showToast("Payment successful!");
  }

  async function handleCancel(auctionId) {
    if (!window.confirm("Cancel this listing? Any current bidder's hold will be released.")) {
      return;
    }
    setActionError(null);
    setBusyId(auctionId);
    try {
      await cancelAuction(auctionId);
      await loadAll();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl animate-pulse space-y-4">
        <div className="h-8 w-40 rounded bg-gray-200 dark:bg-gray-800" />
        <div className="h-32 w-full rounded-xl bg-gray-200 dark:bg-gray-800" />
        <div className="h-32 w-full rounded-xl bg-gray-200 dark:bg-gray-800" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
        Dashboard
      </h1>

      {actionError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
          {actionError}
        </div>
      )}

      <div className="flex flex-col gap-6">
        <Section title="My Listings">
          {listings.length === 0 ? (
            <EmptyRow>You haven't created any listings yet.</EmptyRow>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-white/5">
              {listings.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 py-3">
                  <Link
                    to={`/auctions/${a.id}`}
                    className="flex flex-wrap items-center gap-2 text-sm text-gray-800 hover:text-brand-600 dark:text-gray-200 dark:hover:text-brand-400"
                  >
                    <span className="font-semibold text-gray-900 dark:text-white">${a.current_price}</span>
                    <Badge className={STATUS_BADGE_CLASSES[a.status] || "bg-gray-100 text-gray-600"}>
                      {STATUS_LABELS[a.status] || a.status}
                    </Badge>
                    {a.reserve_met && (
                      <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                        Reserve met
                      </Badge>
                    )}
                  </Link>
                  {RELISTABLE_STATUSES.includes(a.status) && (
                    <SecondaryButton disabled={busyId === a.id} onClick={() => handleRelist(a.id)}>
                      {busyId === a.id ? "Relisting..." : "Relist"}
                    </SecondaryButton>
                  )}
                  {a.status === "Active" && (
                    <SecondaryButton disabled={busyId === a.id} onClick={() => handleCancel(a.id)}>
                      {busyId === a.id ? "Cancelling..." : "Cancel"}
                    </SecondaryButton>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="My Bids">
          {bids.length === 0 ? (
            <EmptyRow>You haven't placed any bids yet.</EmptyRow>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-white/5">
              {bids.map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-3 py-3">
                  <Link
                    to={`/auctions/${b.auction_id}`}
                    className="flex flex-wrap items-center gap-2 text-sm text-gray-800 hover:text-brand-600 dark:text-gray-200 dark:hover:text-brand-400"
                  >
                    <span className="font-semibold text-gray-900 dark:text-white">${b.amount}</span>
                    <Badge className={BID_STATUS_CLASSES[b.status] || "bg-gray-100 text-gray-600"}>
                      {b.status}
                    </Badge>
                    <span className="text-xs text-gray-400">
                      {new Date(b.timestamp).toLocaleString()}
                    </span>
                  </Link>
                  <PayNowButton bid={b} onPay={() => setPayingBid(b)} />
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Notifications">
          {notifications.length === 0 ? (
            <EmptyRow>No notifications yet.</EmptyRow>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-white/5">
              {notifications.map((n) => (
                <li key={n.id} className="flex items-center justify-between gap-3 py-3">
                  <span className="flex items-center gap-2 text-sm">
                    {!n.read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />}
                    <span className={n.read ? "text-gray-500 dark:text-gray-400" : "font-semibold text-gray-900 dark:text-white"}>
                      {NOTIFICATION_LABELS[n.type] || n.type}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(n.sent_at).toLocaleString()}
                    </span>
                  </span>
                  {!n.read && (
                    <SecondaryButton onClick={() => handleMarkRead(n.id)}>Mark read</SecondaryButton>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      {payingBid && (
        <PaymentModal
          amount={payingBid.amount}
          onClose={() => setPayingBid(null)}
          onConfirm={() => handlePay(payingBid.auction_id)}
        />
      )}
    </div>
  );
}

// Shows "Pay Now" only if this bid is active and won (backend confirms via
// the /pay endpoint's own checks, but we avoid showing the button at all
// for bids that obviously aren't winners, to keep the UI honest).
function PayNowButton({ bid, onPay }) {
  if (bid.status !== "active") return null;
  // We don't know the auction's status/payment_status from BidOut alone,
  // so we optimistically show the button for any active bid and let the
  // backend's /pay endpoint reject it if the auction isn't actually Closed
  // or this wasn't the winning bid. A cleaner version would fetch auction
  // status per bid; kept simple here since it's a demo payment stub.
  return (
    <button
      onClick={onPay}
      className="shrink-0 rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600"
    >
      Pay Now
    </button>
  );
}
