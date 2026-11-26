export function generateReferralCode(userId: string): string {
  const normalized = userId.trim().toLowerCase() || "guest";
  let hash = 2166136261;
  for (let i = 0; i < normalized.length; i += 1) {
    hash ^= normalized.charCodeAt(i);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  const suffix = hash.toString(36).toUpperCase().padStart(6, "0").slice(-6);
  return `FIT-${suffix}`;
}

export function buildReferralShareUrl(origin: string, code: string): string {
  const cleanOrigin = origin.trim().replace(/\/+$/, "") || "http://localhost:3000";
  return `${cleanOrigin}/welcome?ref=${encodeURIComponent(code.trim())}`;
}

export function buildWhatsAppInviteUrl(shareUrl: string, userName?: string): string {
  const sender = userName?.trim() || "a friend";
  const text =
    `Assalam-o-Alaikum! Main FitSoul AI use kar raha/rahi hoon — Pakistani khano (roti, daal, sabzi), ` +
    `PCOS/diabetes nutrition targets, workouts aur Face Yoga ke liye best 24/7 AI wellness coach hai. ` +
    `${sender} ki taraf se 7-day Free Trial yahan claim karein: ${shareUrl}`;
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
