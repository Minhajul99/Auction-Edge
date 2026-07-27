import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const inputClasses =
  "mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-800 dark:text-white";
const labelClasses = "text-sm font-medium text-gray-700 dark:text-gray-300";

function EyeIcon({ open }) {
  return open ? (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
      <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
      <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
      <path fillRule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.091 1.092a4 4 0 00-5.557-5.557z" clipRule="evenodd" />
      <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 01-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 010-1.186A10.007 10.007 0 012.839 6.02L6.07 9.252a4 4 0 004.678 4.678z" />
    </svg>
  );
}

function PasswordInput({ id, label, value, onChange, autoComplete, labelExtra }) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <div className="flex items-center justify-between">
        <label htmlFor={id} className={labelClasses}>
          {label}
        </label>
        {labelExtra}
      </div>
      <div className="relative mt-1">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={onChange}
          required
          autoComplete={autoComplete}
          className={`${inputClasses} mt-0 pr-9`}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          tabIndex={-1}
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          <EyeIcon open={visible} />
        </button>
      </div>
    </div>
  );
}

function BrandPanel() {
  const points = [
    "Real-time bidding with live price updates",
    "Soft-close timing so last-second snipes don't work",
    "Wallet holds keep every bid backed by real funds",
  ];
  return (
    <div className="hidden flex-col justify-center gap-6 rounded-2xl bg-linear-to-br from-brand-500 to-brand-700 p-10 text-white lg:flex">
      <div>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 text-lg font-bold">
          A
        </span>
        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Auction<span className="text-brand-100">Edge</span>
        </h1>
        <p className="mt-2 text-brand-100">
          A time-bounded auction platform built for fast, fair bidding.
        </p>
      </div>
      <ul className="flex flex-col gap-3">
        {points.map((p) => (
          <li key={p} className="flex items-start gap-2 text-sm text-brand-50">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 h-4 w-4 shrink-0">
              <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
            </svg>
            {p}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Login() {
  const { login, register, forgotPassword } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("login"); // "login" | "register" | "forgot"
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotResult, setForgotResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(next) {
    setMode(next);
    setError(null);
    setForgotResult(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(firstName, lastName, email, password);
      }
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleForgotSubmit(e) {
    e.preventDefault();
    setError(null);
    setForgotResult(null);
    setSubmitting(true);
    try {
      const result = await forgotPassword(forgotEmail);
      setForgotResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-4xl gap-8 lg:grid-cols-2 lg:items-stretch">
      <BrandPanel />

      <div className="mx-auto w-full max-w-sm self-center">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-gray-900">
          {mode !== "forgot" && (
            <div className="mb-5 flex rounded-lg bg-gray-100 p-1 dark:bg-white/5">
              {["login", "register"].map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => switchMode(m)}
                  className={[
                    "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
                    mode === m
                      ? "bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white"
                      : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200",
                  ].join(" ")}
                >
                  {m === "login" ? "Log In" : "Register"}
                </button>
              ))}
            </div>
          )}

          {mode === "forgot" ? (
            <div className="flex flex-col gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Reset your password
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Enter your account email and we'll send you a reset link.
                </p>
              </div>

              {forgotResult ? (
                <div className="flex flex-col gap-3">
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300">
                    {forgotResult.message}
                  </div>
                  {forgotResult.reset_token && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300">
                      No email service is wired up in this demo, so here's your
                      reset link directly:{" "}
                      <Link
                        to={`/reset-password?token=${encodeURIComponent(forgotResult.reset_token)}`}
                        className="font-semibold underline"
                      >
                        Continue to reset password
                      </Link>
                    </div>
                  )}
                </div>
              ) : (
                <form onSubmit={handleForgotSubmit} className="flex flex-col gap-4">
                  <label htmlFor="forgot-email" className={labelClasses}>
                    Email
                    <input
                      id="forgot-email"
                      type="email"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      required
                      className={inputClasses}
                    />
                  </label>

                  {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
                      {error}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={submitting}
                    className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting ? "Sending..." : "Send Reset Link"}
                  </button>
                </form>
              )}

              <button
                type="button"
                onClick={() => switchMode("login")}
                className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-400"
              >
                &larr; Back to log in
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              {mode === "register" && (
                <div className="grid grid-cols-2 gap-3">
                  <label htmlFor="first-name" className={labelClasses}>
                    First Name
                    <input
                      id="first-name"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      required
                      className={inputClasses}
                    />
                  </label>
                  <label htmlFor="last-name" className={labelClasses}>
                    Last Name
                    <input
                      id="last-name"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      required
                      className={inputClasses}
                    />
                  </label>
                </div>
              )}

              <label htmlFor="email" className={labelClasses}>
                Email
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  className={inputClasses}
                />
              </label>

              <PasswordInput
                id="password"
                label="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                labelExtra={
                  mode === "login" && (
                    <button
                      type="button"
                      onClick={() => switchMode("forgot")}
                      className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400"
                    >
                      Forgot password?
                    </button>
                  )
                }
              />

              {mode === "register" && (
                <PasswordInput
                  id="confirm-password"
                  label="Confirm Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                />
              )}

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Please wait..." : mode === "login" ? "Log In" : "Create Account"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
