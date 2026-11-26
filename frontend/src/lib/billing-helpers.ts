import type { AccessEntitlements } from "@/lib/api";

export type BillingBadgeVariant = "teal" | "amber" | "rose" | "outline";

const PROVIDER_LABELS: Record<string, string> = {
  safepay: "Safepay",
  payfast: "PayFast",
  jazzcash: "JazzCash",
  easypaisa: "Easypaisa",
  lemonsqueezy: "LemonSqueezy",
  mock: "Sandbox Mock",
};

export function formatPlanPrice(
  amount: number,
  currency: "PKR" | "USD",
  durationDays: number,
): string {
  if (amount <= 0) {
    return `Free (${durationDays} days)`;
  }
  const period =
    durationDays >= 60 ? `${Math.round(durationDays / 30)} months` : "month";
  if (currency === "USD") {
    return `$${amount.toFixed(2)} / ${period}`;
  }
  return `Rs. ${Math.round(amount).toLocaleString("en-US")} / ${period}`;
}

export function formatProviderLabel(provider: string | null): string {
  if (!provider) {
    return "Free Trial";
  }
  const key = provider.trim().toLowerCase();
  if (key in PROVIDER_LABELS) {
    return PROVIDER_LABELS[key];
  }
  return provider;
}

export function formatAccessModeBadge(entitlements: AccessEntitlements): {
  label: string;
  variant: BillingBadgeVariant;
} {
  if (!entitlements.is_active) {
    return { label: "Limited Mode", variant: "rose" };
  }
  if (entitlements.is_trial) {
    return { label: "Free Trial Active", variant: "teal" };
  }
  if (entitlements.access_mode === "basic") {
    return { label: "Basic Active", variant: "amber" };
  }
  return { label: "Pro Full Access", variant: "teal" };
}

export function formatTransactionStatus(status: string): {
  label: string;
  variant: BillingBadgeVariant;
} {
  switch (status.trim().toLowerCase()) {
    case "paid":
      return { label: "Paid", variant: "teal" };
    case "pending":
      return { label: "Pending", variant: "amber" };
    case "failed":
      return { label: "Failed", variant: "rose" };
    case "refunded":
      return { label: "Refunded", variant: "outline" };
    default:
      return { label: status || "Unknown", variant: "outline" };
  }
}
