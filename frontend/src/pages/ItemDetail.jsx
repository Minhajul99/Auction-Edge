import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getAuction,
  getBidHistory,
  placeBid,
  acceptHighestBid,
  cancelAuction,
  retractBid,
  getMyBids,
  updateAuctionPhoto,
} from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useAuctionSocket } from "../hooks/useAuctionSocket";
import { useToast } from "../components/Toast";
import { isRetractable } from "../utils/bidWindow";
import { MAX_PHOTO_SIZE_BYTES, fileToDataUrl } from "../utils/image";

function formatRemaining(remaining) {
  const totalSeconds = Math.floor(remaining / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (days > 0 || hours > 0) parts.push(`${hours}h`);
  if (days > 0 || hours > 0 || minutes > 0) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);
  return `${parts.join(" ")} remaining`;
}

function CountdownTimer({ endTime }) {
  const [remaining, setRemaining] = useState(computeRemaining(endTime));

  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining(computeRemaining(endTime));
    }, 1000);
    return () => clearInterval(interval);
  }, [endTime]);

  const ended = remaining <= 0;

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold",
        ended
          ? "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400"
          : remaining < 3 * 60000
            ? "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
            : "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
      ].join(" ")}
    >
      <span className={ended ? "" : "h-1.5 w-1.5 rounded-full bg-current"} />
      {ended ? "Auction ended" : formatRemaining(remaining)}
    </span>
  );
}

function computeRemaining(endTime) {
  return new Date(endTime).getTime() - Date.now();
}

const STATUS_BANNERS = {
  Closed: {
    text: "This auction has ended — Sold",
    classes: "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300",
  },
  "Unsold-NoBids": {
    text: "This auction ended with no bids",
    classes: "bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-300",
  },
  "Unsold-ReserveNotMet": {
    text: "This auction ended — reserve price was not met",
    classes: "bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300",
  },
  Cancelled: {
    text: "This listing was cancelled by the seller",
    classes: "bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-300",
  },
};

export default function ItemDetail() {
  const { auctionId } = useParams();
  const { auth } = useAuth();
  const { showToast } = useToast();
  const [auction, setAuction] = useState(null);
  const [history, setHistory] = useState([]);
  const [bidAmount, setBidAmount] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [live, setLive] = useState(false);
  const [sellerActionError, setSellerActionError] = useState(null);
  const [sellerActionBusy, setSellerActionBusy] = useState(false);
  const [myBid, setMyBid] = useState(null);
  const [retracting, setRetracting] = useState(false);
  const [photoError, setPhotoError] = useState(null);
  const [changingPhoto, setChangingPhoto] = useState(false);
  const prevMyBidStatusRef = useRef(null);

  const refreshMyBid = useCallback(() => {
    if (!auth) return;
    getMyBids()
      .then((bids) => {
        const mine = bids
          .filter((b) => b.auction_id === auctionId)
          .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0];

        if (
          prevMyBidStatusRef.current === "active" &&
          mine &&
          mine.status === "outbid"
        ) {
          showToast("You've been outbid — bid again to stay in the running.", "warning");
        }
        prevMyBidStatusRef.current = mine ? mine.status : null;
        setMyBid(mine || null);
      })
      .catch(() => {});
  }, [auctionId, auth, showToast]);

  const refresh = useCallback(() => {
    getAuction(auctionId).then(setAuction).catch((err) => setError(err.message));
    getBidHistory(auctionId).then(setHistory).catch((err) => setError(err.message));
    refreshMyBid();
  }, [auctionId, refreshMyBid]);

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
    refreshMyBid();
  });

  async function handleRetract() {
    if (!myBid) return;
    setError(null);
    setRetracting(true);
    try {
      await retractBid(auctionId, myBid.id);
      showToast("Bid retracted.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setRetracting(false);
    }
  }

  async function handlePhotoChange(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;

    setPhotoError(null);
    if (!file.type.startsWith("image/")) {
      setPhotoError("Please choose an image file.");
      return;
    }
    if (file.size > MAX_PHOTO_SIZE_BYTES) {
      setPhotoError("Image is too large — please choose one under 2MB.");
      return;
    }

    setChangingPhoto(true);
    try {
      const dataUrl = await fileToDataUrl(file);
      const updated = await updateAuctionPhoto(auctionId, dataUrl);
      setAuction((prev) => (prev ? { ...prev, photo: updated.photo } : prev));
      showToast("Photo updated.");
    } catch (err) {
      setPhotoError(err.message);
    } finally {
      setChangingPhoto(false);
    }
  }

  async function handleBidSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await placeBid(auctionId, parseFloat(bidAmount));
      setBidAmount("");
      showToast("Bid placed successfully!");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAcceptBid() {
    setSellerActionError(null);
    setSellerActionBusy(true);
    try {
      await acceptHighestBid(auctionId);
      showToast("Bid accepted — auction closed as sold!");
      refresh();
    } catch (err) {
      setSellerActionError(err.message);
    } finally {
      setSellerActionBusy(false);
    }
  }

  async function handleCancelListing() {
    setSellerActionError(null);
    setSellerActionBusy(true);
    try {
      await cancelAuction(auctionId);
      showToast("Listing cancelled.");
      refresh();
    } catch (err) {
      setSellerActionError(err.message);
    } finally {
      setSellerActionBusy(false);
    }
  }

  if (!auction) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4">
        <div className="aspect-video w-full rounded-xl bg-gray-200 dark:bg-gray-800" />
        <div className="h-6 w-1/3 rounded bg-gray-200 dark:bg-gray-800" />
      </div>
    );
  }

  const banner = STATUS_BANNERS[auction.status];
  const isSeller = auth && auction.seller_id === auth.user.id;
  const hasActiveBid = Number(auction.current_price) > Number(auction.starting_price);

  return (
    <div className="mx-auto max-w-4xl">
      {live && (
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          Live
        </div>
      )}

      {banner && (
        <div className={`mb-4 rounded-lg px-4 py-3 text-sm font-semibold ${banner.classes}`}>
          {banner.text}
        </div>
      )}

      <h1 className="mb-4 text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
        {auction.title}
      </h1>

      <div className="grid gap-8 md:grid-cols-5">
        <div className="md:col-span-3">
          <div className="relative">
            {auction.photo ? (
              <img
                src={auction.photo}
                alt="Item"
                className="w-full rounded-xl object-cover shadow-sm"
                style={{ maxHeight: 360 }}
              />
            ) : (
              <div className="flex aspect-video w-full items-center justify-center rounded-xl bg-gray-100 text-gray-300 dark:bg-gray-800 dark:text-gray-600">
                No photo
              </div>
            )}

            {isSeller && (
              <label className="absolute right-3 bottom-3 flex cursor-pointer items-center gap-1.5 rounded-md bg-black/60 px-3 py-1.5 text-xs font-semibold text-white backdrop-blur-sm transition-colors hover:bg-black/75">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                  <path fillRule="evenodd" d="M2 6a2 2 0 012-2h1.172a2 2 0 001.414-.586l.828-.828A2 2 0 018.828 2h2.344a2 2 0 011.414.586l.828.828A2 2 0 0014.828 4H16a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm6 6a2 2 0 104 0 2 2 0 00-4 0z" clipRule="evenodd" />
                </svg>
                {changingPhoto ? "Uploading..." : "Change Photo"}
                <input
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  disabled={changingPhoto}
                  className="hidden"
                />
              </label>
            )}
          </div>

          {photoError && (
            <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
              {photoError}
            </div>
          )}

          {auction.description && (
            <p className="mt-4 whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">
              {auction.description}
            </p>
          )}

          <h2 className="mt-6 mb-3 text-lg font-semibold text-gray-900 dark:text-white">
            Bid History
          </h2>
          {history.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">No bids yet — be the first!</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-white/10">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500 dark:bg-white/5 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-2 font-medium">Bidder</th>
                    <th className="px-4 py-2 font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-white/5">
                  {history.map((b, i) => (
                    <tr key={i} className="text-gray-700 dark:text-gray-300">
                      <td className="px-4 py-2">{b.masked_bidder}</td>
                      <td className="px-4 py-2 font-medium text-gray-900 dark:text-white">${b.amount}</td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                        {new Date(b.timestamp).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="md:col-span-2">
          <div className="sticky top-20 rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-gray-900">
            <div className="text-sm text-gray-500 dark:text-gray-400">Current price</div>
            <div className="text-3xl font-bold text-gray-900 dark:text-white">
              ${auction.current_price}
            </div>
            {auction.reserve_met && (
              <div className="mt-1 text-sm font-medium text-emerald-600 dark:text-emerald-400">
                Reserve met
              </div>
            )}

            {auction.status === "Active" && (
              <div className="mt-4">
                <CountdownTimer endTime={auction.end_time} />
              </div>
            )}

            {auction.status === "Active" && (
              <div className="mt-5 border-t border-gray-100 pt-5 dark:border-white/10">
                {isSeller ? (
                  <div className="flex flex-col gap-2">
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      This is your listing.
                    </p>
                    <button
                      type="button"
                      disabled={sellerActionBusy || !hasActiveBid}
                      onClick={handleAcceptBid}
                      title={hasActiveBid ? undefined : "No active bids to accept yet"}
                      className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {sellerActionBusy ? "Working..." : "Accept Highest Bid"}
                    </button>
                    <button
                      type="button"
                      disabled={sellerActionBusy}
                      onClick={handleCancelListing}
                      className="rounded-md border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-900/50 dark:text-red-300 dark:hover:bg-red-950/40"
                    >
                      Cancel Listing
                    </button>
                  </div>
                ) : auth ? (
                  <div className="flex flex-col gap-4">
                    {myBid && myBid.status === "active" && (
                      <div className="flex items-center justify-between gap-3 rounded-lg bg-emerald-50 px-3 py-2 dark:bg-emerald-500/10">
                        <div className="text-sm">
                          <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                            You're leading
                          </span>
                          <span className="text-emerald-600/80 dark:text-emerald-400/80"> — ${myBid.amount}</span>
                        </div>
                        {isRetractable(myBid.timestamp) && (
                          <button
                            type="button"
                            disabled={retracting}
                            onClick={handleRetract}
                            className="shrink-0 rounded-md border border-emerald-300 px-2.5 py-1 text-xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-500/20"
                          >
                            {retracting ? "Retracting..." : "Retract"}
                          </button>
                        )}
                      </div>
                    )}
                    {myBid && myBid.status === "outbid" && (
                      <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
                        You were outbid — your last bid was ${myBid.amount}.
                      </div>
                    )}

                  <form onSubmit={handleBidSubmit} className="flex flex-col gap-3">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Your bid amount
                      <div className="mt-1 flex items-center gap-2">
                        <span className="text-gray-400">$</span>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="0.00"
                          value={bidAmount}
                          onChange={(e) => setBidAmount(e.target.value)}
                          required
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-800 dark:text-white"
                        />
                      </div>
                    </label>
                    <button
                      type="submit"
                      disabled={submitting}
                      className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {submitting ? "Placing bid..." : "Place Bid"}
                    </button>
                  </form>
                  </div>
                ) : (
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    <Link to="/login" className="font-semibold text-brand-600 hover:underline dark:text-brand-400">
                      Log in
                    </Link>{" "}
                    to place a bid.
                  </p>
                )}
              </div>
            )}

            {error && (
              <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
                {error}
              </div>
            )}

            {sellerActionError && (
              <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
                {sellerActionError}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
