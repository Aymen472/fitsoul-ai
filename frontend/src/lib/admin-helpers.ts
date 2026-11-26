export function formatRevenueSummary(pkr: number, usd: number): string {
  const parts: string[] = [];
  if (pkr > 0) {
    parts.push(`Rs. ${Math.round(pkr).toLocaleString("en-US")}`);
  }
  if (usd > 0) {
    parts.push(`$${usd.toFixed(2)}`);
  }
  if (parts.length === 0) {
    return "Rs. 0";
  }
  return parts.join(" + ");
}

export function formatUsdCost(usd: number): string {
  if (usd <= 0) {
    return "$0.00";
  }
  if (usd < 0.01) {
    return `$${usd.toFixed(4)}`;
  }
  return `$${usd.toFixed(2)}`;
}

export function summarizeDeletionCount(recordsRemoved: Record<string, number>): number {
  return Object.values(recordsRemoved).reduce(
    (sum, count) => sum + (Number.isFinite(count) ? count : 0),
    0,
  );
}
