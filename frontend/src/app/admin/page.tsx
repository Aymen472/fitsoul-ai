"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Database,
  DollarSign,
  Edit3,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import {
  ApiError,
  deleteAdminFood,
  getAdminFlaggedMessages,
  getAdminFoods,
  getAdminOverview,
  getAdminUsers,
  upsertAdminFood,
  type AdminFoodItem,
  type AdminOverviewMetrics,
  type AdminUserSummary,
  type FlaggedMessageRecord,
} from "@/lib/api";
import { formatRevenueSummary, formatUsdCost } from "@/lib/admin-helpers";
import { formatMessageTime } from "@/lib/chat-helpers";

type AdminTab = "overview" | "users" | "safety" | "foods";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [adminKey, setAdminKey] = useState("");
  const [overview, setOverview] = useState<AdminOverviewMetrics | null>(null);
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [flaggedMessages, setFlaggedMessages] = useState<FlaggedMessageRecord[]>([]);
  const [foods, setFoods] = useState<AdminFoodItem[]>([]);
  const [foodQuery, setFoodQuery] = useState("");

  // Food editor form state
  const [foodId, setFoodId] = useState("");
  const [foodName, setFoodName] = useState("");
  const [urduName, setUrduName] = useState("");
  const [category, setCategory] = useState("curry");
  const [servingDesc, setServingDesc] = useState("1 cup (200g)");
  const [grams, setGrams] = useState("200");
  const [kcal, setKcal] = useState("220");
  const [protein, setProtein] = useState("12");
  const [carbs, setCarbs] = useState("24");
  const [fat, setFat] = useState("8");
  const [fiber, setFiber] = useState("4");
  const [sodiumMg, setSodiumMg] = useState("380");
  const [giCategory, setGiCategory] = useState<"low" | "medium" | "high">("low");
  const [tagsText, setTagsText] = useState("desi, pcos_friendly");

  const [loading, setLoading] = useState(false);
  const [savingFood, setSavingFood] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadAdminConsole = useCallback(
    async (keyOverride?: string, queryOverride?: string) => {
      const keyToUse = keyOverride !== undefined ? keyOverride : adminKey;
      const queryToUse = queryOverride !== undefined ? queryOverride : foodQuery;
      setLoading(true);
      setError(null);

      const [ovRes, usrRes, flagRes, foodRes] = await Promise.allSettled([
        getAdminOverview(keyToUse),
        getAdminUsers(keyToUse, 50),
        getAdminFlaggedMessages(keyToUse, 50),
        getAdminFoods({ query: queryToUse, limit: 60, adminKey: keyToUse }),
      ]);

      let firstError: string | null = null;

      if (ovRes.status === "fulfilled") {
        setOverview(ovRes.value);
      } else {
        firstError =
          ovRes.reason instanceof ApiError
            ? ovRes.reason.detail
            : "Admin metrics load nahi ho sake.";
      }

      if (usrRes.status === "fulfilled") {
        setUsers(usrRes.value);
      } else if (!firstError) {
        firstError =
          usrRes.reason instanceof ApiError ? usrRes.reason.detail : "Users list load fail.";
      }

      if (flagRes.status === "fulfilled") {
        setFlaggedMessages(flagRes.value);
      }

      if (foodRes.status === "fulfilled") {
        setFoods(foodRes.value);
      }

      if (firstError) {
        setError(firstError);
      }
      setLoading(false);
    },
    [adminKey, foodQuery],
  );

  useEffect(() => {
    void loadAdminConsole("", "");
    // Run initial dev load once on mount; manual key/filter refreshes trigger explicit loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const populateFoodForm = (item: AdminFoodItem) => {
    setFoodId(item.id);
    setFoodName(item.name);
    setUrduName(item.urdu_name);
    setCategory(item.category);
    setServingDesc(item.serving_desc);
    setGrams(String(item.grams));
    setKcal(String(item.kcal));
    setProtein(String(item.protein));
    setCarbs(String(item.carbs));
    setFat(String(item.fat));
    setFiber(String(item.fiber));
    setSodiumMg(String(item.sodium_mg));
    setGiCategory(item.gi_category);
    setTagsText(item.tags.join(", "));
    setNotice(`Editing '${item.name}' (${item.id}).`);
    setError(null);
  };

  const resetFoodForm = () => {
    setFoodId("");
    setFoodName("");
    setUrduName("");
    setCategory("curry");
    setServingDesc("1 cup (200g)");
    setGrams("200");
    setKcal("220");
    setProtein("12");
    setCarbs("24");
    setFat("8");
    setFiber("4");
    setSodiumMg("380");
    setGiCategory("low");
    setTagsText("desi");
  };

  const handleSaveFood = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanedId = foodId.trim();
    if (!cleanedId) {
      setError("Food ID zaroori hai (jaise custom_methi_chicken).");
      return;
    }

    setSavingFood(true);
    setError(null);
    setNotice(null);
    try {
      const tags = tagsText
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);
      const saved = await upsertAdminFood(
        cleanedId,
        {
          name: foodName.trim(),
          urdu_name: urduName.trim(),
          aliases: [],
          category: category.trim(),
          serving_desc: servingDesc.trim(),
          grams: Number(grams) || 100,
          kcal: Number(kcal) || 0,
          protein: Number(protein) || 0,
          carbs: Number(carbs) || 0,
          fat: Number(fat) || 0,
          fiber: Number(fiber) || 0,
          sodium_mg: Number(sodiumMg) || 0,
          gi_category: giCategory,
          tags,
        },
        adminKey,
      );
      setNotice(`Saved '${saved.name}' (${saved.id}) in SQL food catalog.`);
      resetFoodForm();
      await loadAdminConsole(adminKey, foodQuery);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Food item save nahi ho saka.");
    } finally {
      setSavingFood(false);
    }
  };

  const handleDeleteFood = async (idToDelete: string) => {
    setError(null);
    setNotice(null);
    try {
      await deleteAdminFood(idToDelete, adminKey);
      setNotice(`Deleted food '${idToDelete}'.`);
      await loadAdminConsole(adminKey, foodQuery);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Food item delete nahi ho saka.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Admin Operations Console
            </h1>
            <p className="text-xs text-slate-600">
              Users, subscription revenue, estimated AI cost, safety flag review, aur Food DB CRUD
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="password"
            placeholder="Optional X-Admin-Key"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            className="mt-0 w-44 py-1.5 text-xs"
            aria-label="Admin API Key"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={() => void loadAdminConsole(adminKey, foodQuery)}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Inline Feedback Banners */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2">
        {(
          [
            { id: "overview", label: "Overview", icon: Sparkles },
            { id: "users", label: `Users & Billing (${users.length})`, icon: Users },
            {
              id: "safety",
              label: `Safety Review (${flaggedMessages.length})`,
              icon: ShieldAlert,
            },
            { id: "foods", label: `Food DB Editor (${overview?.total_foods ?? foods.length})`, icon: Database },
          ] as const
        ).map(({ id, label, icon: Icon }) => {
          const active = activeTab === id;
          return (
            <Button
              key={id}
              type="button"
              variant={active ? "primary" : "outline"}
              size="sm"
              onClick={() => setActiveTab(id)}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Button>
          );
        })}
      </div>

      {/* Tab 1: Overview KPIs */}
      {activeTab === "overview" && overview && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Registered Users &amp; Profiles</CardDescription>
              <CardTitle className="text-2xl">{overview.total_users}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-600">
              {overview.total_profiles} user(s) completed health onboarding.
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Active Subscriptions</CardDescription>
              <CardTitle className="text-2xl text-[#0f766e]">
                {overview.active_subscriptions}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-2 text-xs">
              <Badge variant="teal">{overview.paid_subscriptions} paid</Badge>
              <Badge variant="amber">{overview.trial_subscriptions} trial</Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription className="text-xs">Collected Revenue</CardDescription>
                <DollarSign className="h-4 w-4 text-[#0f766e]" />
              </div>
              <CardTitle className="text-2xl">
                {formatRevenueSummary(overview.revenue_pkr, overview.revenue_usd)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-600">
              Verified paid orders across PKR local &amp; USD overseas gateways.
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardDescription className="text-xs">Safety Flag Alerts</CardDescription>
                <AlertTriangle className="h-4 w-4 text-rose-600" />
              </div>
              <CardTitle className="text-2xl text-rose-700">
                {overview.flagged_safety_count}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-600">
              Messages flagged by crisis, ED, or medical guardrails across{" "}
              {overview.total_messages} chat turns.
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">Estimated AI Coach Cost</CardDescription>
              <CardTitle className="text-2xl">
                {formatUsdCost(overview.estimated_ai_cost_usd)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-600">
              Avg per user: <strong>{formatUsdCost(overview.avg_ai_cost_per_user_usd)}</strong>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="text-xs">SQL Food Catalog</CardDescription>
              <CardTitle className="text-2xl">{overview.total_foods}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-slate-600">
              Verified South Asian nutrition entries synced for planning &amp; logging.
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab 2: Users & Billing */}
      {activeTab === "users" && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Users, Risk Flags &amp; AI Cost Breakdown</CardTitle>
            <CardDescription className="text-xs">
              Latest 50 users ordered by registration time.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {users.length === 0 ? (
              <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
                Abhi tak koi user register nahi hua hai.
              </p>
            ) : (
              users.map((u) => (
                <div
                  key={u.user_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 px-3.5 py-2.5 text-xs"
                >
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        {u.full_name || "Unnamed User"}
                      </span>
                      <Badge variant={u.subscription_status === "active" ? "teal" : "outline"}>
                        {u.subscription_plan || "limited"} ({u.subscription_status})
                      </Badge>
                      {u.is_high_risk && <Badge variant="rose">High Risk</Badge>}
                      {u.flagged_count > 0 && (
                        <Badge variant="amber">{u.flagged_count} safety flag(s)</Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500">
                      ID: <span className="font-mono">{u.user_id}</span>
                      {u.email ? ` · ${u.email}` : ""}
                      {u.goal ? ` · Goal: ${u.goal}` : ""}
                    </p>
                  </div>
                  <div className="text-right shrink-0 space-y-0.5">
                    <p className="font-semibold text-slate-800">
                      {u.message_count} msgs · {formatUsdCost(u.estimated_ai_cost_usd)}
                    </p>
                    <p className="text-[11px] text-slate-500">{formatMessageTime(u.created_at)}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 3: Safety Review */}
      {activeTab === "safety" && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Flagged Safety Conversations</CardTitle>
            <CardDescription className="text-xs">
              Eating disorder, self-harm, medical risk, ya medication guardrails se trigger hue
              messages.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {flaggedMessages.length === 0 ? (
              <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
                Abhi koi flagged safety conversation nahi hai.
              </p>
            ) : (
              flaggedMessages.map((msg) => (
                <div
                  key={msg.id}
                  className="rounded-xl border border-rose-200 bg-rose-50/40 p-3.5 text-xs space-y-1.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="rose">{msg.role}</Badge>
                      <Badge variant="outline">{msg.channel}</Badge>
                      <span className="font-semibold text-slate-900">
                        {msg.user_full_name || msg.user_id}
                      </span>
                      {msg.user_email && (
                        <span className="text-slate-500">({msg.user_email})</span>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-500">
                      {formatMessageTime(msg.created_at)}
                    </span>
                  </div>
                  <p className="leading-relaxed text-slate-800">{msg.content}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 4: Food DB Editor */}
      {activeTab === "foods" && (
        <div className="grid gap-6 lg:grid-cols-5">
          {/* Add / Edit Form */}
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Add / Edit Food Item</CardTitle>
              <CardDescription className="text-xs">
                Verified macros directly SQL food catalog mein save karein.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveFood} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="food-id" className="text-xs">
                      Food ID
                    </Label>
                    <Input
                      id="food-id"
                      placeholder="custom_methi_chicken"
                      value={foodId}
                      onChange={(e) => setFoodId(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-category" className="text-xs">
                      Category
                    </Label>
                    <Input
                      id="food-category"
                      placeholder="curry"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="food-name" className="text-xs">
                    English Name
                  </Label>
                  <Input
                    id="food-name"
                    placeholder="Methi Chicken"
                    value={foodName}
                    onChange={(e) => setFoodName(e.target.value)}
                    required
                  />
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="food-urdu" className="text-xs">
                      Urdu Name
                    </Label>
                    <Input
                      id="food-urdu"
                      placeholder="میتھی چکن"
                      value={urduName}
                      onChange={(e) => setUrduName(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-serving" className="text-xs">
                      Serving Description
                    </Label>
                    <Input
                      id="food-serving"
                      value={servingDesc}
                      onChange={(e) => setServingDesc(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <Label htmlFor="food-grams" className="text-xs">
                      Grams
                    </Label>
                    <Input
                      id="food-grams"
                      type="number"
                      step="0.1"
                      min="1"
                      value={grams}
                      onChange={(e) => setGrams(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-kcal" className="text-xs">
                      kcal
                    </Label>
                    <Input
                      id="food-kcal"
                      type="number"
                      step="0.1"
                      min="0"
                      value={kcal}
                      onChange={(e) => setKcal(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-gi" className="text-xs">
                      GI
                    </Label>
                    <Select
                      id="food-gi"
                      value={giCategory}
                      onChange={(e) =>
                        setGiCategory(e.target.value as "low" | "medium" | "high")
                      }
                    >
                      <option value="low">low</option>
                      <option value="medium">medium</option>
                      <option value="high">high</option>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2">
                  <div>
                    <Label htmlFor="food-protein" className="text-xs">
                      Prot (g)
                    </Label>
                    <Input
                      id="food-protein"
                      type="number"
                      step="0.1"
                      min="0"
                      value={protein}
                      onChange={(e) => setProtein(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-carbs" className="text-xs">
                      Carb (g)
                    </Label>
                    <Input
                      id="food-carbs"
                      type="number"
                      step="0.1"
                      min="0"
                      value={carbs}
                      onChange={(e) => setCarbs(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-fat" className="text-xs">
                      Fat (g)
                    </Label>
                    <Input
                      id="food-fat"
                      type="number"
                      step="0.1"
                      min="0"
                      value={fat}
                      onChange={(e) => setFat(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="food-sodium" className="text-xs">
                      Na (mg)
                    </Label>
                    <Input
                      id="food-sodium"
                      type="number"
                      step="1"
                      min="0"
                      value={sodiumMg}
                      onChange={(e) => setSodiumMg(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="food-tags" className="text-xs">
                    Tags (comma separated)
                  </Label>
                  <Input
                    id="food-tags"
                    value={tagsText}
                    onChange={(e) => setTagsText(e.target.value)}
                  />
                </div>

                <div className="flex items-center justify-between gap-2 pt-1">
                  <Button type="button" variant="ghost" size="sm" onClick={resetFoodForm}>
                    Clear
                  </Button>
                  <Button type="submit" size="sm" disabled={savingFood}>
                    <Plus className="h-3.5 w-3.5" />
                    {savingFood ? "Saving..." : "Save Food Item"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Searchable Food List */}
          <Card className="lg:col-span-3">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Pakistani Food Catalog ({foods.length})</CardTitle>
              <div className="flex items-center gap-2 pt-1">
                <Input
                  placeholder="Search roti, daal, biryani..."
                  value={foodQuery}
                  onChange={(e) => setFoodQuery(e.target.value)}
                  className="mt-0 text-xs"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void loadAdminConsole(adminKey, foodQuery)}
                >
                  <Search className="h-3.5 w-3.5" />
                  Search
                </Button>
              </div>
            </CardHeader>
            <CardContent className="max-h-[560px] space-y-2 overflow-y-auto">
              {foods.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2 text-xs"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="font-semibold text-slate-900">{item.name}</span>
                      <Badge variant="outline">{item.category}</Badge>
                      <Badge variant={item.gi_category === "low" ? "teal" : "amber"}>
                        {item.gi_category} GI
                      </Badge>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      <span className="font-mono">{item.id}</span> · {item.serving_desc} ·{" "}
                      {item.kcal} kcal (P {item.protein}g / C {item.carbs}g / F {item.fat}g)
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => populateFoodForm(item)}
                      aria-label={`Edit ${item.name}`}
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => void handleDeleteFood(item.id)}
                      aria-label={`Delete ${item.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-rose-600" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
