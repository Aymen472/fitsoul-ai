import { describe, expect, it } from "vitest";

import {
  formatRevenueSummary,
  formatUsdCost,
  summarizeDeletionCount,
} from "@/lib/admin-helpers";

describe("admin-helpers", () => {
  it("formats combined PKR and USD revenue summaries", () => {
    expect(formatRevenueSummary(5998, 9.99)).toBe("Rs. 5,998 + $9.99");
    expect(formatRevenueSummary(2999, 0)).toBe("Rs. 2,999");
    expect(formatRevenueSummary(0, 19.98)).toBe("$19.98");
    expect(formatRevenueSummary(0, 0)).toBe("Rs. 0");
  });

  it("formats AI cost estimates cleanly", () => {
    expect(formatUsdCost(0)).toBe("$0.00");
    expect(formatUsdCost(0.0009)).toBe("$0.0009");
    expect(formatUsdCost(1.234)).toBe("$1.23");
  });

  it("sums total removed records across tables", () => {
    expect(
      summarizeDeletionCount({
        users: 1,
        profiles: 1,
        meal_logs: 4,
        messages: 6,
      }),
    ).toBe(12);
    expect(summarizeDeletionCount({})).toBe(0);
  });
});
