// Mirrors core/bidding.py's is_retractable: a hard 15-minute window
// measured from the original bid timestamp.
export const RETRACTION_WINDOW_MS = 15 * 60 * 1000;

export function isRetractable(bidTimestamp) {
  return Date.now() - new Date(bidTimestamp).getTime() <= RETRACTION_WINDOW_MS;
}
