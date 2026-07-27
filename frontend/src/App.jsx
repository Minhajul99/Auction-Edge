import { BrowserRouter, Routes, Route, Link, NavLink, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./components/Toast";
import Browse from "./pages/Browse";
import ItemDetail from "./pages/ItemDetail";
import CreateListing from "./pages/CreateListing";
import Login from "./pages/Login";
import ResetPassword from "./pages/ResetPassword";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 shrink-0">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500 text-white font-bold text-sm shadow-sm shadow-brand-500/30">
        A
      </span>
      <span className="text-lg font-semibold tracking-tight text-gray-900 dark:text-white">
        Auction<span className="text-brand-500">Edge</span>
      </span>
    </Link>
  );
}

function navLinkClasses({ isActive }) {
  return [
    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
    isActive
      ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-white/10 dark:hover:text-white",
  ].join(" ");
}

function NavBar() {
  const { auth, logout } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-gray-200/80 bg-white/80 backdrop-blur-md dark:border-white/10 dark:bg-gray-950/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <Logo />

        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={navLinkClasses}>
            Browse
          </NavLink>
          {auth && (
            <NavLink to="/create" className={navLinkClasses}>
              Create Listing
            </NavLink>
          )}
          {auth && (
            <NavLink to="/dashboard" className={navLinkClasses}>
              Dashboard
            </NavLink>
          )}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {auth ? (
            <>
              <Link
                to="/profile"
                className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10"
              >
                {auth.user.avatar ? (
                  <img
                    src={auth.user.avatar}
                    alt=""
                    className="h-6 w-6 rounded-full object-cover"
                  />
                ) : (
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-[10px] font-bold text-white">
                    {(auth.user.first_name?.[0] || "") + (auth.user.last_name?.[0] || "")}
                  </span>
                )}
                <span className="hidden sm:inline">
                  {auth.user.first_name} {auth.user.last_name}
                </span>
              </Link>
              <button
                onClick={logout}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-white/15 dark:text-gray-200 dark:hover:bg-white/10"
              >
                Log Out
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="rounded-md bg-brand-500 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600"
            >
              Log In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-gray-200 py-6 text-center text-sm text-gray-400 dark:border-white/10 dark:text-gray-500">
      AuctionEdge — a time-bounded auction platform, built for ENGI 9839.
    </footer>
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
      <ToastProvider>
        <BrowserRouter>
          <div className="flex min-h-svh flex-col bg-gray-50 dark:bg-gray-950">
            <NavBar />
            <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
              <Routes>
                <Route path="/" element={<Browse />} />
                <Route path="/auctions/:auctionId" element={<ItemDetail />} />
                <Route path="/login" element={<Login />} />
                <Route path="/reset-password" element={<ResetPassword />} />
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
                <Route
                  path="/profile"
                  element={
                    <RequireAuth>
                      <Profile />
                    </RequireAuth>
                  }
                />
              </Routes>
            </main>
            <Footer />
          </div>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
