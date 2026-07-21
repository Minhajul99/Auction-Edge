import { useState } from "react";

const inputClasses =
  "mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-800 dark:text-white";
const labelClasses = "block text-sm font-medium text-gray-700 dark:text-gray-300";

// Cosmetic only -- groups digits into "1234 5678 9012 3456" as the user types.
function formatCardNumber(value) {
  const digits = value.replace(/\D/g, "").slice(0, 16);
  return digits.replace(/(.{4})/g, "$1 ").trim();
}

function formatExpiry(value) {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}/${digits.slice(2)}`;
}

export default function PaymentModal({ amount, onClose, onConfirm }) {
  const [cardName, setCardName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvv, setCvv] = useState("");
  const [zip, setZip] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      // This is a dummy checkout form -- no card details are sent anywhere
      // or validated against a real payment processor. It exists purely to
      // give the "Pay Now" flow a realistic e-commerce feel; the actual
      // charge is the existing wallet-hold-to-charge stub on the backend.
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Payment Details</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-white/10 dark:hover:text-gray-300"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <div className="mb-4 flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3 dark:bg-white/5">
          <span className="text-sm text-gray-500 dark:text-gray-400">Total due</span>
          <span className="text-xl font-bold text-gray-900 dark:text-white">${amount}</span>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className={labelClasses}>
            Name on card
            <input
              value={cardName}
              onChange={(e) => setCardName(e.target.value)}
              required
              placeholder="Jane Doe"
              className={inputClasses}
            />
          </label>

          <label className={labelClasses}>
            Card number
            <input
              value={cardNumber}
              onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
              required
              inputMode="numeric"
              placeholder="1234 5678 9012 3456"
              maxLength={19}
              className={inputClasses}
            />
          </label>

          <div className="grid grid-cols-3 gap-3">
            <label className={`${labelClasses} col-span-1`}>
              Expiry
              <input
                value={expiry}
                onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                required
                inputMode="numeric"
                placeholder="MM/YY"
                maxLength={5}
                className={inputClasses}
              />
            </label>
            <label className={`${labelClasses} col-span-1`}>
              CVV
              <input
                value={cvv}
                onChange={(e) => setCvv(e.target.value.replace(/\D/g, "").slice(0, 4))}
                required
                inputMode="numeric"
                placeholder="123"
                maxLength={4}
                className={inputClasses}
              />
            </label>
            <label className={`${labelClasses} col-span-1`}>
              ZIP
              <input
                value={zip}
                onChange={(e) => setZip(e.target.value.slice(0, 10))}
                required
                placeholder="A1A 1A1"
                className={inputClasses}
              />
            </label>
          </div>

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
            {submitting ? "Processing payment..." : `Pay $${amount}`}
          </button>

          <p className="text-center text-xs text-gray-400">
            This is a demo checkout — no real payment is processed.
          </p>
        </form>
      </div>
    </div>
  );
}
