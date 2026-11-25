"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, ShieldAlert } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import {
  ApiError,
  createOrUpsertProfile,
  type ActivityLevel,
  type DietType,
  type Gender,
  type Goal,
  type HighRiskCondition,
  type MedicalCondition,
  type ProfileRecord,
} from "@/lib/api";

const MEDICAL_CONDITION_OPTIONS: { value: MedicalCondition; label: string; femaleOnly?: boolean }[] = [
  { value: "pcos", label: "PCOS / Hormonal Balance", femaleOnly: true },
  { value: "diabetes_t2", label: "Type-2 Diabetes (Sugar Control)" },
  { value: "hypertension", label: "Hypertension (High BP / Low Sodium)" },
  { value: "hypothyroid", label: "Hypothyroidism (Thyroid Support)" },
];

const HIGH_RISK_OPTIONS: { value: HighRiskCondition; label: string }[] = [
  { value: "diabetes_t1", label: "Type-1 Diabetes" },
  { value: "kidney_disease", label: "Kidney Disease" },
  { value: "liver_disease", label: "Liver Disease" },
  { value: "eating_disorder_history", label: "History of Eating Disorder" },
];

function splitCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

export default function OnboardingPage() {
  const { user, profileRecord, isLoading, setProfileRecord } = useAuth();

  const [fullName, setFullName] = useState("");
  const [age, setAge] = useState("28");
  const [gender, setGender] = useState<Gender>("female");
  const [heightCm, setHeightCm] = useState("165");
  const [weightKg, setWeightKg] = useState("75");
  const [targetWeightKg, setTargetWeightKg] = useState("");
  const [activityLevel, setActivityLevel] = useState<ActivityLevel>("sedentary");
  const [goal, setGoal] = useState<Goal>("lose");
  const [dietType, setDietType] = useState<DietType>("non_veg");
  const [timezone, setTimezone] = useState("Asia/Karachi");
  const [conditions, setConditions] = useState<MedicalCondition[]>(["pcos"]);
  const [highRiskConditions, setHighRiskConditions] = useState<HighRiskCondition[]>([]);
  const [isPregnant, setIsPregnant] = useState(false);
  const [onRegularMedication, setOnRegularMedication] = useState(false);
  const [allergiesText, setAllergiesText] = useState("");
  const [dislikesText, setDislikesText] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedResult, setSavedResult] = useState<ProfileRecord | null>(null);

  useEffect(() => {
    if (profileRecord) {
      const p = profileRecord.profile;
      setFullName(profileRecord.full_name ?? user?.fullName ?? "");
      setAge(String(p.age));
      setGender(p.gender);
      setHeightCm(String(p.height_cm));
      setWeightKg(String(p.weight_kg));
      setTargetWeightKg(p.target_weight_kg ? String(p.target_weight_kg) : "");
      setActivityLevel(p.activity_level);
      setGoal(p.goal);
      setDietType(p.diet_type);
      setTimezone(p.timezone || "Asia/Karachi");
      setConditions(p.conditions);
      setHighRiskConditions(p.high_risk_conditions);
      setIsPregnant(p.is_pregnant);
      setOnRegularMedication(p.on_regular_medication);
      setAllergiesText(p.allergies.join(", "));
      setDislikesText(p.dislikes.join(", "));
    } else if (user) {
      setFullName(user.fullName);
    }
  }, [profileRecord, user]);

  const handleGenderChange = (nextGender: Gender) => {
    setGender(nextGender);
    if (nextGender === "male") {
      setConditions((prev) => prev.filter((item) => item !== "pcos"));
      setIsPregnant(false);
    }
  };

  const toggleCondition = (value: MedicalCondition) => {
    setConditions((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    );
  };

  const toggleHighRisk = (value: HighRiskCondition) => {
    setHighRiskConditions((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) {
      return;
    }
    setError(null);
    setSavedResult(null);

    const parsedAge = Number(age);
    const parsedHeight = Number(heightCm);
    const parsedWeight = Number(weightKg);
    const parsedTargetWeight = targetWeightKg.trim() ? Number(targetWeightKg) : null;

    if (parsedTargetWeight !== null) {
      if (goal === "lose" && parsedTargetWeight >= parsedWeight) {
        setError("Weight loss goal ke liye target weight current weight se kam hona chahiye.");
        return;
      }
      if (goal === "gain" && parsedTargetWeight <= parsedWeight) {
        setError("Weight gain goal ke liye target weight current weight se zyada hona chahiye.");
        return;
      }
    }

    setSubmitting(true);
    try {
      const record = await createOrUpsertProfile({
        user_id: user.id,
        email: user.email,
        full_name: fullName.trim() || user.fullName,
        profile: {
          age: parsedAge,
          gender,
          height_cm: parsedHeight,
          weight_kg: parsedWeight,
          target_weight_kg: parsedTargetWeight,
          activity_level: activityLevel,
          goal,
          conditions,
          high_risk_conditions: highRiskConditions,
          is_pregnant: gender === "female" ? isPregnant : false,
          on_regular_medication: onRegularMedication,
          diet_type: dietType,
          allergies: splitCommaList(allergiesText),
          dislikes: splitCommaList(dislikesText),
          timezone,
        },
      });
      setProfileRecord(record);
      setSavedResult(record);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Backend server se connect nahi ho saka. Check karein ke FastAPI chal raha hai.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!isLoading && !user) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in first to save your profile</CardTitle>
          <CardDescription>
            Pehle sign in kar lein taake aap ke health profile aur deterministic calories safely
            save ho sakein.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/login">
            <Button>
              Go to Sign In
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Health & Nutrition Profile
        </h1>
        <p className="text-sm text-slate-600">
          FastAPI deterministic engine aap ki exact BMR, TDEE, calorie floor, aur medical rules
          calculate karta hai.
        </p>
      </div>

      {savedResult && (
        <Card className="border-[#0f766e]/30 bg-[#f0f7f4]">
          <CardHeader>
            <div className="flex items-center gap-2 text-[#0f766e]">
              <CheckCircle2 className="h-5 w-5" />
              <CardTitle>Profile Saved & Targets Computed!</CardTitle>
            </div>
            <CardDescription className="text-slate-700">
              Daily Target: <strong>{savedResult.targets.calories} kcal</strong> • Protein{" "}
              <strong>{savedResult.targets.protein_g}g</strong> • Carbs{" "}
              <strong>{savedResult.targets.carbs_g}g</strong> • Fat{" "}
              <strong>{savedResult.targets.fat_g}g</strong> • Water{" "}
              <strong>{savedResult.targets.water_ml} ml</strong>
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Link href="/">
              <Button>
                View Wellness Hub
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>1. Basic Details & Measurements</CardTitle>
            <CardDescription>Accurate measurements se exact clinical BMR nikalta hai.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="onboard-name">Full Name</Label>
              <Input
                id="onboard-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>

            <div>
              <Label htmlFor="onboard-age">Age (18–80)</Label>
              <Input
                id="onboard-age"
                type="number"
                min={18}
                max={80}
                value={age}
                onChange={(e) => setAge(e.target.value)}
                required
              />
            </div>

            <div>
              <Label htmlFor="onboard-gender">Biological Sex (for BMR & floor rules)</Label>
              <Select
                id="onboard-gender"
                value={gender}
                onChange={(e) => handleGenderChange(e.target.value as Gender)}
              >
                <option value="female">Female (1200 kcal safety floor)</option>
                <option value="male">Male (1500 kcal safety floor)</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="onboard-timezone">Timezone</Label>
              <Select
                id="onboard-timezone"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
              >
                <option value="Asia/Karachi">Asia/Karachi (PKT)</option>
                <option value="Asia/Dubai">Asia/Dubai (GST)</option>
                <option value="Europe/London">Europe/London (UK)</option>
                <option value="America/New_York">America/New_York (EST)</option>
                <option value="UTC">UTC</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="onboard-height">Height (cm, 120–220)</Label>
              <Input
                id="onboard-height"
                type="number"
                step="0.1"
                min={120}
                max={220}
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                required
              />
            </div>

            <div>
              <Label htmlFor="onboard-weight">Current Weight (kg, 30–250)</Label>
              <Input
                id="onboard-weight"
                type="number"
                step="0.1"
                min={30}
                max={250}
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                required
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>2. Goal, Activity & Desi Diet Preference</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="onboard-goal">Primary Goal</Label>
              <Select
                id="onboard-goal"
                value={goal}
                onChange={(e) => setGoal(e.target.value as Goal)}
              >
                <option value="lose">Healthy Weight Loss</option>
                <option value="maintain">Maintain & Energize</option>
                <option value="gain">Healthy Muscle / Weight Gain</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="onboard-target-weight">Target Weight (kg, optional)</Label>
              <Input
                id="onboard-target-weight"
                type="number"
                step="0.1"
                min={30}
                max={250}
                placeholder="e.g. 65"
                value={targetWeightKg}
                onChange={(e) => setTargetWeightKg(e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="onboard-activity">Daily Activity Level</Label>
              <Select
                id="onboard-activity"
                value={activityLevel}
                onChange={(e) => setActivityLevel(e.target.value as ActivityLevel)}
              >
                <option value="sedentary">Sedentary (Desk work, minimal exercise)</option>
                <option value="light">Light (1–3 days light walk/workout)</option>
                <option value="moderate">Moderate (3–5 days exercise)</option>
                <option value="active">Active (6–7 days training)</option>
                <option value="very_active">Very Active (Physical job + daily training)</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="onboard-diet">Diet Preference</Label>
              <Select
                id="onboard-diet"
                value={dietType}
                onChange={(e) => setDietType(e.target.value as DietType)}
              >
                <option value="non_veg">Non-Veg (Chicken, Fish, Mutton, Eggs, Daal)</option>
                <option value="eggetarian">Eggetarian (Eggs + Veg / Daal)</option>
                <option value="veg">Vegetarian (Daal, Sabzi, Paneer, Dahi)</option>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>3. Medical Conditions & Safety Guardrails</CardTitle>
            <CardDescription>
              Strict clinical macro caps aur safe-mode locks automatically apply hote hain.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <p className="mb-2 text-sm font-medium text-slate-800">Supported Nutrition Rules</p>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {MEDICAL_CONDITION_OPTIONS.map((opt) => {
                  const disabled = Boolean(opt.femaleOnly && gender === "male");
                  const checked = conditions.includes(opt.value);
                  return (
                    <label
                      key={opt.value}
                      className="flex items-center gap-2.5 rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm cursor-pointer has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => toggleCondition(opt.value)}
                        className="h-4 w-4 rounded accent-[#0f766e]"
                      />
                      <span>{opt.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                <ShieldAlert className="h-4 w-4" />
                <span>Safety Flags (Doctor-Supervision & Supplement Lockout)</span>
                <Badge variant="amber">Clinical Safety</Badge>
              </div>

              <div className="grid gap-2.5 sm:grid-cols-2">
                <label className="flex items-center gap-2.5 text-sm text-slate-800 cursor-pointer has-[:disabled]:opacity-50">
                  <input
                    type="checkbox"
                    checked={isPregnant}
                    disabled={gender === "male"}
                    onChange={(e) => setIsPregnant(e.target.checked)}
                    className="h-4 w-4 rounded accent-[#0f766e]"
                  />
                  <span>Currently Pregnant (Zero calorie deficit)</span>
                </label>

                <label className="flex items-center gap-2.5 text-sm text-slate-800 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={onRegularMedication}
                    onChange={(e) => setOnRegularMedication(e.target.checked)}
                    className="h-4 w-4 rounded accent-[#0f766e]"
                  />
                  <span>On Regular Prescription Medication</span>
                </label>

                {HIGH_RISK_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2.5 text-sm text-slate-800 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={highRiskConditions.includes(opt.value)}
                      onChange={() => toggleHighRisk(opt.value)}
                      className="h-4 w-4 rounded accent-[#0f766e]"
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="onboard-allergies">Food Allergies (comma-separated)</Label>
                <Input
                  id="onboard-allergies"
                  placeholder="e.g. peanuts, shellfish"
                  value={allergiesText}
                  onChange={(e) => setAllergiesText(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="onboard-dislikes">Disliked Foods (comma-separated)</Label>
                <Input
                  id="onboard-dislikes"
                  placeholder="e.g. karela, okra"
                  value={dislikesText}
                  onChange={(e) => setDislikesText(e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {error && (
          <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </p>
        )}

        <div className="flex justify-end">
          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? "Calculating & Saving..." : "Save Profile & Calculate Targets"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
