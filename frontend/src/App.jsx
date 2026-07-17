import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Browse from "./pages/Browse";
import ItemDetail from "./pages/ItemDetail";
import CreateListing from "./pages/CreateListing";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";

function NavBar() {
  const { auth, logout } = useAuth();
  return (
    <nav
      style={{
        padding: "1rem",
        borderBottom: "1px solid #eee",
        marginBottom: "1rem",
        display: "flex",
        gap: "1rem",
        alignItems: "center",
      }}
    >
      <Link to="/">AuctionEdge</Link>
      {auth && <Link to="/create">Create Listing</Link>}
      {auth && <Link to="/dashboard">Dashboard</Link>}
      <div style={{ marginLeft: "auto" }}>
        {auth ? (
          <>
            <span style={{ marginRight: "1rem" }}>{auth.user.email}</span>
            <button onClick={logout}>Log Out</button>
          </>
        ) : (
          <Link to="/login">Log In</Link>
        )}
      </div>
    </nav>
  );
}

function RequireAuth({ children }) {
  const { auth } = useAuth();
  if (!auth) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <NavBar />
        <div style={{ padding: "0 1rem" }}>
          <Routes>
            <Route path="/" element={<Browse />} />
            <Route path="/auctions/:auctionId" element={<ItemDetail />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/create"
              element={
                <RequireAuth>
                  <CreateListing />
                </RequireAuth>
              }
            />
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <Dashboard />
                </RequireAuth>
              }
            />
          </Routes>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}
