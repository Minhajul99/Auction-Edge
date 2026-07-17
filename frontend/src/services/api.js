const BASE_URL = "http://127.0.0.1:8000";

function getToken() {
  const saved = localStorage.getItem("auctionedge_auth");
  return saved ? JSON.parse(saved).token : null;
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
      detail = body.detail || detail;
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

export function listAuctions(statusFilter) {
  const query = statusFilter ? `?status_filter=${statusFilter}` : "";
  return request(`/auctions${query}`);
}

export function getAuction(auctionId) {
  return request(`/auctions/${auctionId}`);
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
