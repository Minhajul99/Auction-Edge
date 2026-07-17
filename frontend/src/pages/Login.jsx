import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("login"); // "login" | "register"
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
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

  return (
    <div style={{ maxWidth: 360, margin: "0 auto" }}>
      <h1>{mode === "login" ? "Log In" : "Register"}</h1>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {mode === "register" && (
          <>
            <label>
              First Name
              <input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
              />
            </label>
            <label>
              Last Name
              <input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
              />
            </label>
          </>
        )}

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && <p style={{ color: "red" }}>{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Please wait..." : mode === "login" ? "Log In" : "Register"}
        </button>
      </form>

      <p style={{ marginTop: "1rem" }}>
        {mode === "login" ? (
          <>
            Don't have an account?{" "}
            <button onClick={() => setMode("register")} style={{ background: "none", border: "none", color: "blue", cursor: "pointer" }}>
              Register
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button onClick={() => setMode("login")} style={{ background: "none", border: "none", color: "blue", cursor: "pointer" }}>
              Log In
            </button>
          </>
        )}
      </p>
    </div>
  );
}
