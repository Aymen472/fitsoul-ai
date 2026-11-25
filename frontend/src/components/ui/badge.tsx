import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "teal" | "amber" | "rose" | "outline";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const BADGE_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-800 border-transparent",
  teal: "bg-[#f0f7f4] text-[#0f766e] border-[#0f766e]/20",
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  rose: "bg-rose-50 text-rose-800 border-rose-200",
  outline: "bg-white text-slate-700 border-slate-300",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        BADGE_CLASSES[variant],
        className,
      )}
      {...props}
    />
  );
}
