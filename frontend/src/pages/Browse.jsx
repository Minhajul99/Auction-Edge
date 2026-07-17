import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAuctions } from "../services/api";

export default function Browse() {
  const [auctions, setAuctions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listAuctions("Active")
      .then(setAuctions)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading auctions...</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;
  if (auctions.length === 0) return <p>No active auctions right now.</p>;

  return (
    <div>
      <h1>AuctionEdge — Browse</h1>
      <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
        {auctions.map((a) => (
          <Link
            key={a.id}
            to={`/auctions/${a.id}`}
            style={{
              border: "1px solid #ccc",
              borderRadius: 8,
              overflow: "hidden",
              textDecoration: "none",
              color: "inherit",
              display: "block",
            }}
          >
            {a.photo ? (
              <img
                src={a.photo}
                alt=""
                style={{ width: "100%", height: 140, objectFit: "cover", display: "block" }}
              />
            ) : (
              <div style={{ width: "100%", height: 140, background: "#eee" }} />
            )}
            <div style={{ padding: "0.75rem" }}>
              <div>Current price: ${a.current_price}</div>
              <div style={{ fontSize: "0.85rem", color: "#666" }}>
                Ends: {new Date(a.end_time).toLocaleString()}
              </div>
              {a.reserve_met && (
                <div style={{ color: "green", fontSize: "0.85rem" }}>Reserve met</div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
