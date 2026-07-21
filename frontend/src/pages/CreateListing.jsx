import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createItem, createAuction } from "../services/api";
import { useToast } from "../components/Toast";
import { CATEGORIES, DURATIONS } from "../constants";

// Keep uploaded images reasonably small since they're stored as base64
// strings in the DB (no external file storage / CDN set up yet).
const MAX_PHOTO_SIZE_BYTES = 2 * 1024 * 1024; // 2 MB

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const inputClasses =
  "mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-800 dark:text-white";
const labelClasses = "block text-sm font-medium text-gray-700 dark:text-gray-300";

export default function CreateListing() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [photoDataUrl, setPhotoDataUrl] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [startingPrice, setStartingPrice] = useState("");
  const [reservePrice, setReservePrice] = useState("");
  const [durationDays, setDurationDays] = useState(DURATIONS[0]);

  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handlePhotoChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }
    if (file.size > MAX_PHOTO_SIZE_BYTES) {
      setError("Image is too large — please choose one under 2MB.");
      return;
    }

    setError(null);
    const dataUrl = await fileToDataUrl(file);
    setPhotoDataUrl(dataUrl);
    setPhotoPreview(dataUrl);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!photoDataUrl) {
      setError("A photo is required.");
      return;
    }

    setSubmitting(true);
    try {
      const item = await createItem({
        title,
        description: description || null,
        category,
        photos: [photoDataUrl],
      });

      const auction = await createAuction({
        item_id: item.id,
        starting_price: parseFloat(startingPrice),
        reserve_price: reservePrice ? parseFloat(reservePrice) : null,
        duration_days: Number(durationDays),
      });

      showToast("Listing created successfully!");
      navigate(`/auctions/${auction.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
        Create Listing
      </h1>
      <p className="mt-1 mb-6 text-sm text-gray-500 dark:text-gray-400">
        List an item for auction — set a starting price and let bidders take it from there.
      </p>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-5 rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-gray-900"
      >
        <label className={labelClasses}>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required className={inputClasses} />
        </label>

        <label className={labelClasses}>
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className={inputClasses}
          />
        </label>

        <label className={labelClasses}>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputClasses}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>

        <div>
          <label className={labelClasses}>Photo</label>
          <label className="mt-1 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 px-4 py-8 text-center transition-colors hover:border-brand-400 hover:bg-brand-50/50 dark:border-white/15 dark:hover:border-brand-500 dark:hover:bg-brand-500/5">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
              Click to upload a photo
            </span>
            <span className="text-xs text-gray-400">PNG or JPG, up to 2MB</span>
            <input type="file" accept="image/*" onChange={handlePhotoChange} required className="hidden" />
          </label>
          {photoPreview && (
            <img
              src={photoPreview}
              alt="Preview"
              className="mt-3 max-h-48 rounded-lg border border-gray-200 object-cover dark:border-white/10"
            />
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <label className={labelClasses}>
            Starting Price ($)
            <input
              type="number"
              step="0.01"
              value={startingPrice}
              onChange={(e) => setStartingPrice(e.target.value)}
              required
              className={inputClasses}
            />
          </label>

          <label className={labelClasses}>
            Duration
            <select value={durationDays} onChange={(e) => setDurationDays(e.target.value)} className={inputClasses}>
              {DURATIONS.map((d) => (
                <option key={d} value={d}>{d} days</option>
              ))}
            </select>
          </label>
        </div>

        <label className={labelClasses}>
          Reserve Price ($) <span className="font-normal text-gray-400">— optional, must exceed starting price</span>
          <input
            type="number"
            step="0.01"
            value={reservePrice}
            onChange={(e) => setReservePrice(e.target.value)}
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
          {submitting ? "Creating..." : "Create Listing"}
        </button>
      </form>
    </div>
  );
}
