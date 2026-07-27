export const BASE_URL = "http://127.0.0.1:8000";

function getToken() {
  const saved = localStorage.getItem("auctionedge_auth");
  return saved ? JSON.parse(saved).token : null;
}

// FastAPI's `detail` field is a plain string for our own HTTPException
// raises (e.g. "Insufficient funds: ..."), but a LIST of Pydantic error
// objects for 422 validation failures (e.g. reserve_price <= starting_price).
// Passing that list straight into `new Error(...)` silently stringifies it
// to "[object Object]" -- this extracts a readable message from either shape.
export function extractErrorDetail(body, fallback) {
  const detail = body?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e.msg || JSON.stringify(e)).replace(/^Value error,\s*/, ""))
      .join("; ");
  }
  return fallback;
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = extractErrorDetail(body, detail);
    } catch {
      // response wasn't JSON, ignore
    }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

// --- Users ---
export function getUser(userId) {
  return request(`/users/${userId}`);
}

export function getNotifications(userId) {
  return request(`/users/${userId}/notifications`);
}

export function markNotificationRead(userId, notificationId) {
  return request(`/users/${userId}/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

// --- Items & Auctions ---
export function createItem(item) {
  return request("/auctions/items", {
    method: "POST",
    body: JSON.stringify(item),
  });
}

export function createAuction(auction) {
  return request("/auctions", {
    method: "POST",
    body: JSON.stringify(auction),
  });
}

export function listAuctions(statusFilter, category, opts = {}) {
  const { minPrice, maxPrice, page, pageSize } = opts;
  const params = new URLSearchParams();
  if (statusFilter) params.set("status_filter", statusFilter);
  if (category) params.set("category", category);
  if (minPrice != null && minPrice !== "") params.set("min_price", minPrice);
  if (maxPrice != null && maxPrice !== "") params.set("max_price", maxPrice);
  if (page != null) params.set("page", page);
  if (pageSize != null) params.set("page_size", pageSize);
  const query = params.toString() ? `?${params.toString()}` : "";
  return request(`/auctions${query}`);
}

export function getAuction(auctionId) {
  return request(`/auctions/${auctionId}`);
}

export function acceptHighestBid(auctionId) {
  return request(`/auctions/${auctionId}/accept-bid`, { method: "POST" });
}

export function cancelAuction(auctionId) {
  return request(`/auctions/${auctionId}/cancel`, { method: "POST" });
}

// --- Bids ---
export function placeBid(auctionId, amount) {
  return request(`/auctions/${auctionId}/bids`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
}

export function retractBid(auctionId, bidId) {
  return request(`/auctions/${auctionId}/bids/${bidId}/retract`, {
    method: "POST",
  });
}

export function getBidHistory(auctionId) {
  return request(`/auctions/${auctionId}/bids/history`);
}

export function getMyBids() {
  return request("/auctions/bids/mine");
}

// --- Wallet ---
export function getWallet() {
  return request("/wallet/me");
}
