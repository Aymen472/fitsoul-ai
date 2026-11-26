"use client";

import { ShoppingBasket, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { GroceryItem } from "@/lib/api";
import { computeGroceryProgress, groupGroceryByCategory } from "@/lib/meal-plan-helpers";
import { cn } from "@/lib/utils";

interface GroceryListPanelProps {
  items: GroceryItem[];
  checkedMap: Record<string, boolean>;
  onToggleItem: (foodId: string) => void;
  onClearChecked: () => void;
}

export function GroceryListPanel({
  items,
  checkedMap,
  onToggleItem,
  onClearChecked,
}: GroceryListPanelProps) {
  const groups = groupGroceryByCategory(items);
  const progress = computeGroceryProgress(items, checkedMap);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShoppingBasket className="h-4 w-4 text-[#0f766e]" />
            <CardTitle className="text-base">7-Day Grocery List</CardTitle>
          </div>
          <Badge variant="teal">
            {progress.checked}/{progress.total}
          </Badge>
        </div>
        <CardDescription className="text-xs">
          Pure 7 din ke plan se auto-calculated sabzi, daal, protein aur kitchen staples.
        </CardDescription>

        {progress.total > 0 && (
          <div className="mt-2 space-y-1.5">
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-[#0f766e] transition-all duration-300"
                style={{ width: `${progress.percent}%` }}
              />
            </div>
            {progress.checked > 0 && (
              <div className="flex justify-end">
                <Button variant="ghost" size="sm" onClick={onClearChecked}>
                  <Trash2 className="h-3.5 w-3.5" />
                  Clear Checked
                </Button>
              </div>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {groups.length === 0 ? (
          <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
            Generate your weekly meal plan to build your shopping list automatically.
          </p>
        ) : (
          <div className="max-h-[65vh] space-y-4 overflow-y-auto pr-1">
            {groups.map((group) => (
              <div key={group.category} className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  {group.label}
                </p>
                <ul className="space-y-1.5">
                  {group.items.map((item) => {
                    const isChecked = Boolean(checkedMap[item.food_id]);
                    return (
                      <li key={item.food_id}>
                        <label
                          className={cn(
                            "flex items-start gap-2.5 rounded-xl border px-3 py-2 text-xs transition-colors cursor-pointer",
                            isChecked
                              ? "border-slate-200/70 bg-slate-50 text-slate-400"
                              : "border-slate-200 bg-white text-slate-800 hover:bg-[#f0f7f4]/40",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => onToggleItem(item.food_id)}
                            className="mt-0.5 h-4 w-4 rounded accent-[#0f766e]"
                          />
                          <div className="min-w-0 flex-1">
                            <p
                              className={cn(
                                "font-medium",
                                isChecked && "line-through text-slate-400",
                              )}
                            >
                              {item.name}
                              {item.urdu_name ? (
                                <span className="ml-1.5 font-normal text-slate-500">
                                  ({item.urdu_name})
                                </span>
                              ) : null}
                            </p>
                            <p className="mt-0.5 text-[11px] text-slate-500">
                              {item.total_grams}g • {item.total_servings} servings
                            </p>
                          </div>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
