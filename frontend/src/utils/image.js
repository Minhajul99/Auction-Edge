// Kept small since photos are stored as base64 strings directly in the DB
// (no external file storage / CDN set up yet).
export const MAX_PHOTO_SIZE_BYTES = 2 * 1024 * 1024; // 2 MB

export function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
