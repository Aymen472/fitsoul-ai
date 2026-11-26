import { describe, expect, it } from "vitest";

import {
  buildReferralShareUrl,
  buildWhatsAppInviteUrl,
  generateReferralCode,
} from "@/lib/referral-helpers";

describe("referral-helpers", () => {
  it("generates a deterministic FIT-XXXXXX referral code", () => {
    const code1 = generateReferralCode("user-aymen-1");
    const code2 = generateReferralCode("user-aymen-1");
    const code3 = generateReferralCode("different-user");

    expect(code1).toMatch(/^FIT-[0-9A-Z]{6}$/);
    expect(code1).toBe(code2);
    expect(code1).not.toBe(code3);
  });

  it("builds referral share landing URLs cleanly", () => {
    expect(buildReferralShareUrl("https://app.fitsoul.pk/", "FIT-ABC123")).toBe(
      "https://app.fitsoul.pk/welcome?ref=FIT-ABC123",
    );
  });

  it("builds URL-encoded WhatsApp invite links with share URL and sender name", () => {
    const invite = buildWhatsAppInviteUrl(
      "https://app.fitsoul.pk/welcome?ref=FIT-ABC123",
      "Aymen",
    );
    expect(invite.startsWith("https://wa.me/?text=")).toBe(true);
    const decoded = decodeURIComponent(invite.replace("https://wa.me/?text=", ""));
    expect(decoded).toContain("Aymen");
    expect(decoded).toContain("https://app.fitsoul.pk/welcome?ref=FIT-ABC123");
  });
});
