"use client";

import {
  CheckCircle2,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
  Sparkles,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkoutRoutine } from "@/lib/api";
import {
  estimateWorkoutCalories,
  formatTimer,
  formatWorkoutCategory,
  speakCue,
} from "@/lib/workout-helpers";

interface GuidedWorkoutPlayerProps {
  routine: WorkoutRoutine;
  weightKg: number;
  onComplete: (durationMinutes: number) => Promise<void>;
  onClose: () => void;
}

export function GuidedWorkoutPlayer({
  routine,
  weightKg,
  onComplete,
  onClose,
}: GuidedWorkoutPlayerProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [phase, setPhase] = useState<"work" | "rest" | "complete">("work");
  const [secondsLeft, setSecondsLeft] = useState(routine.steps[0]?.duration_sec ?? 45);
  const [isRunning, setIsRunning] = useState(true);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [useEasierAlternative, setUseEasierAlternative] = useState(false);
  const [logging, setLogging] = useState(false);
  const [loggedSuccess, setLoggedSuccess] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);

  useEffect(() => {
    setStepIndex(0);
    setPhase("work");
    setSecondsLeft(routine.steps[0]?.duration_sec ?? 45);
    setIsRunning(true);
    setUseEasierAlternative(false);
    setLoggedSuccess(false);
    setLogError(null);
  }, [routine]);

  useEffect(() => {
    if (!isRunning || phase === "complete") {
      return;
    }
    const id = window.setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(id);
  }, [isRunning, phase]);

  useEffect(() => {
    if (secondsLeft > 0 || phase === "complete") {
      return;
    }

    const currentStep = routine.steps[stepIndex];
    const nextStep = routine.steps[stepIndex + 1];

    if (phase === "work") {
      if (currentStep && currentStep.rest_sec > 0 && nextStep) {
        setPhase("rest");
        setSecondsLeft(currentStep.rest_sec);
        speakCue(
          `Rest for ${currentStep.rest_sec} seconds. Next is ${nextStep.name}.`,
          voiceEnabled,
        );
        return;
      }
      if (nextStep) {
        setStepIndex((idx) => idx + 1);
        setPhase("work");
        setSecondsLeft(nextStep.duration_sec);
        setUseEasierAlternative(false);
        speakCue(`Next exercise: ${nextStep.name}`, voiceEnabled);
        return;
      }
      setPhase("complete");
      setIsRunning(false);
      speakCue("Shabash! Session complete!", voiceEnabled);
      return;
    }

    if (phase === "rest") {
      if (nextStep) {
        setStepIndex((idx) => idx + 1);
        setPhase("work");
        setSecondsLeft(nextStep.duration_sec);
        setUseEasierAlternative(false);
        speakCue(`Start ${nextStep.name}`, voiceEnabled);
      } else {
        setPhase("complete");
        setIsRunning(false);
        speakCue("Shabash! Session complete!", voiceEnabled);
      }
    }
  }, [secondsLeft, phase, stepIndex, routine.steps, voiceEnabled]);

  const currentStep = routine.steps[stepIndex];
  const nextStep = routine.steps[stepIndex + 1];
  const phaseDuration =
    phase === "rest"
      ? Math.max(1, currentStep?.rest_sec ?? 15)
      : Math.max(1, currentStep?.duration_sec ?? 45);
  const progressFraction =
    phase === "complete" ? 1 : Math.max(0, Math.min(1, secondsLeft / phaseDuration));

  const radius = 56;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - progressFraction);
  const estCalories = estimateWorkoutCalories(
    routine.met_value,
    weightKg,
    routine.duration_minutes,
  );

  const handleRestartStep = () => {
    if (!currentStep) {
      return;
    }
    setPhase("work");
    setSecondsLeft(currentStep.duration_sec);
    setIsRunning(true);
  };

  const handleSkip = () => {
    if (nextStep) {
      setStepIndex((idx) => idx + 1);
      setPhase("work");
      setSecondsLeft(nextStep.duration_sec);
      setUseEasierAlternative(false);
    } else {
      setPhase("complete");
      setSecondsLeft(0);
      setIsRunning(false);
    }
  };

  const handleToggleVoice = () => {
    setVoiceEnabled((prev) => {
      const next = !prev;
      if (next && currentStep) {
        speakCue(`Voice cues active. ${currentStep.name}`, true);
      }
      return next;
    });
  };

  const handleLogSession = async () => {
    setLogging(true);
    setLogError(null);
    try {
      await onComplete(routine.duration_minutes);
      setLoggedSuccess(true);
    } catch {
      setLogError("Session log save nahi ho saka — dobara koshish karein.");
    } finally {
      setLogging(false);
    }
  };

  return (
    <Card className="border-[#0f766e]/30 bg-gradient-to-br from-white via-white to-[#f0f7f4]/80">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="teal">{formatWorkoutCategory(routine.workout_type)}</Badge>
              <Badge variant="amber">~{estCalories} kcal</Badge>
              <Badge variant="outline">
                Step {Math.min(stepIndex + 1, routine.steps.length)} of {routine.steps.length}
              </Badge>
            </div>
            <CardTitle className="text-xl">{routine.name}</CardTitle>
            <CardDescription>{routine.urdu_subtitle}</CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleToggleVoice}
              aria-label="Toggle voice cues"
            >
              {voiceEnabled ? <Volume2 className="h-4 w-4 text-[#0f766e]" /> : <VolumeX className="h-4 w-4" />}
              {voiceEnabled ? "Voice On" : "Voice Off"}
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close workout player">
              <X className="h-4 w-4" />
              Close
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {phase === "complete" ? (
          <div className="rounded-2xl border border-[#0f766e]/25 bg-[#f0f7f4] p-6 text-center space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#0f766e] text-white">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-slate-900">Shabash! Session Complete</h3>
              <p className="text-sm text-slate-600">
                {routine.duration_minutes} minutes • ~{estCalories} kcal MET burn at {weightKg} kg
              </p>
            </div>

            {loggedSuccess ? (
              <p className="text-sm font-semibold text-[#0f766e]">
                Workout logged aur streak update ho gaya!
              </p>
            ) : (
              <Button size="lg" disabled={logging} onClick={() => void handleLogSession()}>
                <CheckCircle2 className="h-4 w-4" />
                {logging ? "Logging Session..." : "Save & Log Session"}
              </Button>
            )}
          </div>
        ) : (
          <div className="grid items-center gap-6 md:grid-cols-[170px_minmax(0,1fr)]">
            {/* Circular Countdown Ring */}
            <div className="relative mx-auto flex h-36 w-36 items-center justify-center">
              <svg viewBox="0 0 140 140" className="h-36 w-36 -rotate-90">
                <circle cx="70" cy="70" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="10" />
                <circle
                  cx="70"
                  cy="70"
                  r={radius}
                  fill="none"
                  stroke={phase === "rest" ? "#d97706" : "#0f766e"}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={dashOffset}
                  className="transition-all duration-300"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold tracking-tight text-slate-900">
                  {formatTimer(secondsLeft)}
                </span>
                <span
                  className={`text-[11px] font-semibold uppercase tracking-wide ${
                    phase === "rest" ? "text-[#d97706]" : "text-[#0f766e]"
                  }`}
                >
                  {phase === "rest" ? "Rest" : "Active"}
                </span>
              </div>
            </div>

            {/* Step Instructions + Easier Alternative Toggle */}
            <div className="space-y-3">
              {phase === "rest" ? (
                <div className="space-y-1.5">
                  <Badge variant="amber">Rest & Breathe</Badge>
                  <h3 className="text-lg font-bold text-slate-900">
                    Next up: {nextStep?.name ?? "Cooldown"}
                  </h3>
                  <p className="text-sm text-slate-600">
                    Halka sa paani piyein aur agle step ke liye ready ho jayein.
                  </p>
                </div>
              ) : currentStep ? (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-bold text-slate-900">
                      {useEasierAlternative && currentStep.easier_alternative_name
                        ? currentStep.easier_alternative_name
                        : currentStep.name}
                    </h3>
                    {useEasierAlternative && <Badge variant="amber">Joint-Safe Swap</Badge>}
                  </div>
                  <p className="text-sm leading-relaxed text-slate-700">
                    {useEasierAlternative && currentStep.easier_alternative_instructions
                      ? currentStep.easier_alternative_instructions
                      : currentStep.instructions}
                  </p>

                  {currentStep.easier_alternative_name && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setUseEasierAlternative((prev) => !prev)}
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      {useEasierAlternative
                        ? "Back to Standard Move"
                        : "Too Hard? Switch to Easier Move"}
                    </Button>
                  )}
                </div>
              ) : null}

              {/* Player Controls */}
              <div className="flex flex-wrap gap-2 pt-2">
                <Button size="sm" onClick={() => setIsRunning((prev) => !prev)}>
                  {isRunning ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  {isRunning ? "Pause" : "Resume"}
                </Button>
                <Button variant="outline" size="sm" onClick={handleRestartStep}>
                  <RotateCcw className="h-4 w-4" />
                  Restart Step
                </Button>
                <Button variant="outline" size="sm" onClick={handleSkip}>
                  <SkipForward className="h-4 w-4" />
                  Skip Step
                </Button>
                <Button
                  variant={loggedSuccess ? "secondary" : "outline"}
                  size="sm"
                  disabled={logging || loggedSuccess}
                  onClick={() => void handleLogSession()}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {loggedSuccess ? "Logged!" : "Finish & Log Now"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {logError && (
          <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {logError}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
