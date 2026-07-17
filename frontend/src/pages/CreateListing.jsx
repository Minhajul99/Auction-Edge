import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createItem, createAuction } from "../services/api";

const CATEGORIES = ["Gaming", "Photography", "Audio", "Computers"];
const DURATIONS = [3, 5, 7, 10];

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

export default function CreateListing() {
  const navigate = useNavigate();

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

      navigate(`/auctions/${auction.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 480, margin: "0 auto" }}>
      <h1>Create Listing</h1>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>

        <label>
          Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>

        <label>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>

        <label>
          Photo (upload from your computer)
          <input type="file" accept="image/*" onChange={handlePhotoChange} required />
        </label>

        {photoPreview && (
          <img
            src={photoPreview}
            alt="Preview"
            style={{ maxWidth: "100%", maxHeight: 200, borderRadius: 8 }}
          />
        )}

        <label>
          Starting Price ($)
          <input
            type="number"
            step="0.01"
            value={startingPrice}
            onChange={(e) => setStartingPrice(e.target.value)}
            required
          />
        </label>

        <label>
          Reserve Price ($) — optional, must be higher than starting price
          <input
            type="number"
            step="0.01"
            value={reservePrice}
            onChange={(e) => setReservePrice(e.target.value)}
          />
        </label>

        <label>
          Duration
          <select value={durationDays} onChange={(e) => setDurationDays(e.target.value)}>
            {DURATIONS.map((d) => (
              <option key={d} value={d}>{d} days</option>
            ))}
          </select>
        </label>

        {error && <p style={{ color: "red" }}>{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Creating..." : "Create Listing"}
        </button>
      </form>
    </div>
  );
}
