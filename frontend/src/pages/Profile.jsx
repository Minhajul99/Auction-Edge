import { useEffect, useState } from "react";
import { getMyProfile, updateProfile, getWallet, depositFunds } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import { MAX_PHOTO_SIZE_BYTES, fileToDataUrl } from "../utils/image";

const inputClasses =
  "mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-800 dark:text-white";
const labelClasses = "text-sm font-medium text-gray-700 dark:text-gray-300";

function Section({ title, children }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-gray-900">
      <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
      {children}
    </section>
  );
}

function StatTile({ label, value, accent }) {
  return (
    <div className="rounded-lg bg-gray-50 p-4 dark:bg-white/5">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold ${accent || "text-gray-900 dark:text-white"}`}>
        {value}
      </div>
    </div>
  );
}

function Avatar({ src, name, size = 96 }) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const style = { width: size, height: size };

  if (src) {
    return (
      <img
        src={src}
        alt="Profile"
        style={style}
        className="rounded-full object-cover shadow-sm ring-2 ring-white dark:ring-gray-900"
      />
    );
  }
  return (
    <div
      style={style}
      className="flex items-center justify-center rounded-full bg-brand-500 text-2xl font-bold text-white shadow-sm ring-2 ring-white dark:ring-gray-900"
    >
      {initials || "?"}
    </div>
  );
}

export default function Profile() {
  const { updateUser } = useAuth();
  const { showToast } = useToast();

  const [profile, setProfile] = useState(null);
  const [wallet, setWallet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState(null);

  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState(null);

  const [depositAmount, setDepositAmount] = useState("");
  const [depositing, setDepositing] = useState(false);
  const [depositError, setDepositError] = useState(null);

  useEffect(() => {
    Promise.all([getMyProfile(), getWallet()])
      .then(([p, w]) => {
        setProfile(p);
        setWallet(w);
        setFirstName(p.first_name);
        setLastName(p.last_name);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleAvatarChange(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setAvatarError(null);
    if (!file.type.startsWith("image/")) {
      setAvatarError("Please choose an image file.");
      return;
    }
    if (file.size > MAX_PHOTO_SIZE_BYTES) {
      setAvatarError("Image is too large — please choose one under 2MB.");
      return;
    }

    setUploadingAvatar(true);
    try {
      const dataUrl = await fileToDataUrl(file);
      const updated = await updateProfile({ avatar: dataUrl });
      setProfile(updated);
      updateUser({ avatar: updated.avatar });
      showToast("Profile picture updated.");
    } catch (err) {
      setAvatarError(err.message);
    } finally {
      setUploadingAvatar(false);
    }
  }

  async function handleNameSubmit(e) {
    e.preventDefault();
    setNameError(null);
    setSavingName(true);
    try {
      const updated = await updateProfile({ first_name: firstName, last_name: lastName });
      setProfile(updated);
      updateUser({ first_name: updated.first_name, last_name: updated.last_name });
      showToast("Profile updated.");
    } catch (err) {
      setNameError(err.message);
    } finally {
      setSavingName(false);
    }
  }

  async function handleDeposit(e) {
    e.preventDefault();
    setDepositError(null);
    const amount = parseFloat(depositAmount);
    if (!amount || amount <= 0) {
      setDepositError("Enter an amount greater than 0.");
      return;
    }
    setDepositing(true);
    try {
      const updated = await depositFunds(amount);
      setWallet(updated);
      setDepositAmount("");
      showToast(`Added $${amount.toFixed(2)} to your wallet.`);
    } catch (err) {
      setDepositError(err.message);
    } finally {
      setDepositing(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl animate-pulse space-y-4">
        <div className="h-32 w-full rounded-xl bg-gray-200 dark:bg-gray-800" />
        <div className="h-40 w-full rounded-xl bg-gray-200 dark:bg-gray-800" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
        {error}
      </div>
    );
  }

  const fullName = `${profile.first_name} ${profile.last_name}`;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
        Profile
      </h1>

      <Section title="Profile Picture">
        <div className="flex items-center gap-5">
          <Avatar src={profile.avatar} name={fullName} />
          <div>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-white/15 dark:text-gray-200 dark:hover:bg-white/10">
              {uploadingAvatar ? "Uploading..." : "Change Picture"}
              <input
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
                disabled={uploadingAvatar}
                className="hidden"
              />
            </label>
            <p className="mt-2 text-xs text-gray-400">PNG or JPG, up to 2MB.</p>
            {avatarError && (
              <p className="mt-2 text-xs text-red-600 dark:text-red-400">{avatarError}</p>
            )}
          </div>
        </div>
      </Section>

      <Section title="Account Details">
        <form onSubmit={handleNameSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClasses}>
              First Name
              <input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
                className={inputClasses}
              />
            </label>
            <label className={labelClasses}>
              Last Name
              <input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
                className={inputClasses}
              />
            </label>
          </div>

          <div>
            <span className={labelClasses}>Email</span>
            <div className="mt-1 flex items-center gap-2">
              <input value={profile.email} disabled className={`${inputClasses} mt-0 disabled:opacity-60`} />
              {profile.email_verified ? (
                <span className="shrink-0 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                  Verified
                </span>
              ) : (
                <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                  Unverified
                </span>
              )}
            </div>
          </div>

          {nameError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
              {nameError}
            </div>
          )}

          <button
            type="submit"
            disabled={savingName}
            className="self-start rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {savingName ? "Saving..." : "Save Changes"}
          </button>
        </form>
      </Section>

      <Section title="Wallet">
        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Balance" value={`$${wallet.balance}`} />
          <StatTile label="Held" value={`$${wallet.held_amount}`} accent="text-amber-600 dark:text-amber-400" />
          <StatTile label="Available" value={`$${wallet.available}`} accent="text-emerald-600 dark:text-emerald-400" />
        </div>

        <form onSubmit={handleDeposit} className="mt-4 flex items-end gap-2">
          <label className={`${labelClasses} flex-1`}>
            Add funds (demo)
            <div className="mt-1 flex items-center gap-2">
              <span className="text-gray-400">$</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                placeholder="0.00"
                className={`${inputClasses} mt-0`}
              />
            </div>
          </label>
          <button
            type="submit"
            disabled={depositing}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/15 dark:text-gray-200 dark:hover:bg-white/10"
          >
            {depositing ? "Adding..." : "Add Funds"}
          </button>
        </form>
        {depositError && (
          <p className="mt-2 text-xs text-red-600 dark:text-red-400">{depositError}</p>
        )}
        <p className="mt-2 text-xs text-gray-400">
          No real payment gateway is connected — this simulates a top-up for testing.
        </p>
      </Section>
    </div>
  );
}
