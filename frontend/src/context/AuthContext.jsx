import { createContext, useContext, useState, useEffect } from "react";
import { extractErrorDetail } from "../services/api";

const AuthContext = createContext(null);

const BASE_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "auctionedge_auth";

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : null;
  });

  useEffect(() => {
    if (auth) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [auth]);

  async function register(firstName, lastName, email, password) {
    const res = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email,
        password,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(extractErrorDetail(body, "Registration failed"));
    }
    const data = await res.json();
    setAuth({ token: data.access_token, user: data.user });
  }

  async function login(email, password) {
    // OAuth2PasswordRequestForm expects form-encoded data, not JSON.
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);

    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(extractErrorDetail(body, "Login failed"));
    }
    const data = await res.json();
    setAuth({ token: data.access_token, user: data.user });
  }

  async function forgotPassword(email) {
    const res = await fetch(`${BASE_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(extractErrorDetail(body, "Something went wrong. Please try again."));
    }
    return res.json(); // { message, reset_token? } -- reset_token only set in debug mode
  }

  async function resetPassword(token, newPassword) {
    const res = await fetch(`${BASE_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: newPassword }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(extractErrorDetail(body, "Reset failed"));
    }
    const data = await res.json();
    setAuth({ token: data.access_token, user: data.user });
  }

  function updateUser(partialUser) {
    setAuth((prev) => (prev ? { ...prev, user: { ...prev.user, ...partialUser } } : prev));
  }

  function logout() {
    setAuth(null);
  }

  return (
    <AuthContext.Provider
      value={{ auth, login, register, logout, forgotPassword, resetPassword, updateUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
