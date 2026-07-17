import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { getAuction, getBidHistory, placeBid } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useAuctionSocket } from "../hooks/useAuctionSocket";

function CountdownTimer({ endTime }) {
  const [remaining, setRemaining] = useState(computeRemaining(endTime));

  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining(computeRemaining(endTime));
    }, 1000);
    return () => clearInterval(interval);
  }, [endTime]);

  if (remaining <= 0) return <span style={{ color: "red" }}>Auction ended</span>;

  const minutes = Math.floor(remaining / 60000);
  const seconds = Math.floor((remaining % 60000) / 1000);
  return (
    <span>
      {minutes}m {seconds}s remaining
    </span>
  );
}

function computeRemaining(endTime) {
  return new Date(endTime).getTime() - Date.now();
}

const STATUS_BANNERS = {
  Closed: { text: "This auction has ended — Sold", color: "#1a7f37", bg: "#e6f4ea" },
  "Unsold-NoBids": { text: "This auction ended with no bids", color: "#7a7a7a", bg: "#f0f0f0" },
  "Unsold-ReserveNotMet": { text: "This auction ended — reserve price was not met", color: "#a15c00", bg: "#fff3e0" },
};

export default function ItemDetail() {
  const { auctionId } = useParams();
  const { auth } = useAuth();
  const [auction, setAuction] = useState(null);
  const [item, setItem] = useState(null);
  const [history, setHistory] = useState([]);
  const [bidAmount, setBidAmount] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [live, setLive] = useState(false);

  const refresh = useCallback(() => {
    getAuction(auctionId).then(setAuction).catch((err) => setError(err.message));
    getBidHistory(auctionId).then(setHistory).catch((err) => setError(err.message));
  }, [auctionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useAuctionSocket(auctionId, (payload) => {
    setLive(true);
    setAuction((prev) =>
      prev
        ? {
            ...prev,
            current_price: payload.current_price,
            end_time: payload.end_time,
            status: payload.status,
            reserve_met: payload.reserve_met,
          }
        : prev
    );
    getBidHistory(auctionId).then(setHistory).catch(() => {});
  });

  async function handleBidSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await placeBid(auctionId, parseFloat(bidAmount));
      setBidAmount("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!auction) return <p>Loading...</p>;

  const banner = STATUS_BANNERS[auction.status];

  return (
    <div style={{ maxWidth: 600, margin: "0 auto" }}>
      <h1>
        Auction Item{" "}
        {live && (
          <span style={{ fontSize: "0.7rem", color: "green", fontWeight: "normal" }}>
            ● live
          </span>
        )}
      </h1>

      {banner && (
        <div
          style={{
            background: banner.bg,
            color: banner.color,
            padding: "0.75rem 1rem",
            borderRadius: 6,
            marginBottom: "1rem",
            fontWeight: "bold",
          }}
        >
          {banner.text}
        </div>
      )}

      {auction.photo && (
        <img
          src={auction.photo}
          alt="Item"
          style={{ width: "100%", maxHeight: 320, objectFit: "cover", borderRadius: 8, marginBottom: "1rem" }}
        />
      )}

      <p>
        <strong>Current price:</strong> ${auction.current_price}
      </p>
      <p>
        <strong>Status:</strong> {auction.status}
        {auction.reserve_met && <span style={{ color: "green" }}> · Reserve met</span>}
      </p>
      <p>
        <CountdownTimer endTime={auction.end_time} />
      </p>

      {auction.status === "Active" && (
        auth ? (
          <form onSubmit={handleBidSubmit} style={{ marginBottom: "1.5rem" }}>
            <input
              type="number"
              step="0.01"
              placeholder="Your bid amount"
              value={bidAmount}
              onChange={(e) => setBidAmount(e.target.value)}
              required
            />
            <button type="submit" disabled={submitting}>
              {submitting ? "Placing bid..." : "Place Bid"}
            </button>
          </form>
        ) : (
          <p>
            <Link to="/login">Log in</Link> to place a bid.
          </p>
        )
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}

      <h2>Bid History</h2>
      {history.length === 0 ? (
        <p>No bids yet — be the first!</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Bidder</th>
              <th style={{ textAlign: "left" }}>Amount</th>
              <th style={{ textAlign: "left" }}>Time</th>
            </tr>
          </thead>
          <tbody>
            {history.map((b, i) => (
              <tr key={i}>
                <td>{b.masked_bidder}</td>
                <td>${b.amount}</td>
                <td>{new Date(b.timestamp).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
