"""Curated home fitness and face yoga routines with MET-based calorie calculation."""

from enum import StrEnum

from pydantic import BaseModel, Field

DEFAULT_FITNESS_MET = 3.5
DEFAULT_FACE_YOGA_MET = 1.6


class WorkoutCategory(StrEnum):
    """Supported guided session categories."""

    FITNESS = "fitness"
    FACE_YOGA = "face_yoga"


class DifficultyLevel(StrEnum):
    """Routine intensity tier."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"


class WorkoutStep(BaseModel):
    """Single timed movement or pose inside a guided routine."""

    id: str
    name: str
    instructions: str
    duration_sec: int = Field(ge=10, le=300)
    rest_sec: int = Field(ge=0, le=120)
    muscle_groups: list[str]
    contraindications: list[str] = Field(default_factory=list)
    easier_alternative_name: str | None = None
    easier_alternative_instructions: str | None = None


class WorkoutRoutine(BaseModel):
    """Complete home workout or face yoga session with MET metadata."""

    id: str
    name: str
    urdu_subtitle: str
    workout_type: WorkoutCategory
    level: DifficultyLevel
    duration_minutes: int = Field(gt=0)
    met_value: float = Field(gt=0)
    focus_areas: list[str]
    contraindications: list[str] = Field(default_factory=list)
    description: str
    steps: list[WorkoutStep] = Field(min_length=1)


def calculate_calories_burned_met(
    met_value: float,
    weight_kg: float,
    duration_minutes: int | float,
) -> float:
    """Compute deterministic calories burned using kcal = MET * weight_kg * hours."""
    if met_value <= 0 or weight_kg <= 0 or duration_minutes <= 0:
        raise ValueError("met_value, weight_kg, and duration_minutes must be positive")
    return round(met_value * weight_kg * (float(duration_minutes) / 60.0), 1)


WORKOUT_ROUTINES: tuple[WorkoutRoutine, ...] = (
    WorkoutRoutine(
        id="pcos_low_impact_cardio",
        name="PCOS Hormone-Balance Walk & Tone",
        urdu_subtitle="Ghar par bina kisi machine ke low-impact energy routine",
        workout_type=WorkoutCategory.FITNESS,
        level=DifficultyLevel.BEGINNER,
        duration_minutes=15,
        met_value=4.0,
        focus_areas=["insulin_sensitivity", "full_body", "stress_relief"],
        contraindications=[],
        description=(
            "Gentle steady movement designed for PCOS & blood-sugar balance without spiking stress "
            "cortisol."
        ),
        steps=[
            WorkoutStep(
                id="march_warm_up",
                name="Brisk March in Place",
                instructions=(
                    "Stand tall, swing arms comfortably, and lift knees lightly at a steady pace."
                ),
                duration_sec=60,
                rest_sec=15,
                muscle_groups=["legs", "cardio"],
                easier_alternative_name="Seated Arm & Heel Taps",
                easier_alternative_instructions=(
                    "Sit upright on a sturdy chair and alternate heel taps with gentle arm swings."
                ),
            ),
            WorkoutStep(
                id="step_touch_reach",
                name="Side Step Touch & Overhead Reach",
                instructions=(
                    "Step side-to-side smoothly while reaching both arms up softly "
                    "to open the chest."
                ),
                duration_sec=50,
                rest_sec=15,
                muscle_groups=["shoulders", "glutes", "cardio"],
                easier_alternative_name="Side Steps Without Overhead Reach",
                easier_alternative_instructions=(
                    "Keep hands on hips and step slowly side-to-side."
                ),
            ),
            WorkoutStep(
                id="wall_pushups",
                name="Wall Push-ups",
                instructions=(
                    "Place palms flat on a wall shoulder-width apart, bend elbows cleanly, "
                    "and press back."
                ),
                duration_sec=45,
                rest_sec=20,
                muscle_groups=["chest", "arms", "core"],
                easier_alternative_name="Standing Closer Wall Press",
                easier_alternative_instructions=(
                    "Step closer to the wall for lighter resistance and slower reps."
                ),
            ),
            WorkoutStep(
                id="glute_bridge_hold",
                name="Gentle Hip Glute Bridges",
                instructions=(
                    "Lie on your back with knees bent, lift hips slowly, squeeze glutes for 2s, "
                    "and lower down."
                ),
                duration_sec=45,
                rest_sec=20,
                muscle_groups=["glutes", "core", "lower_back"],
                easier_alternative_name="Mini Pelvic Tilts",
                easier_alternative_instructions=(
                    "Keep hips close to the mat and gently tilt your pelvis upward without strain."
                ),
            ),
            WorkoutStep(
                id="deep_belly_breath",
                name="Deep Belly Cooldown Breathing",
                instructions=(
                    "Inhale slowly through the nose for 4 seconds, exhale softly for 6 seconds "
                    "to calm cortisol."
                ),
                duration_sec=60,
                rest_sec=0,
                muscle_groups=["recovery", "nervous_system"],
                easier_alternative_name="Seated Box Breathing",
                easier_alternative_instructions=(
                    "Sit comfortably with eyes closed and breathe gently at your own rhythm."
                ),
            ),
        ],
    ),
    WorkoutRoutine(
        id="fat_burn_home_circuit",
        name="Metabolic Home Fat-Burn Circuit",
        urdu_subtitle="20-minute energizing full-body bodyweight circuit",
        workout_type=WorkoutCategory.FITNESS,
        level=DifficultyLevel.INTERMEDIATE,
        duration_minutes=20,
        met_value=5.5,
        focus_areas=["fat_loss", "stamina", "legs_core"],
        contraindications=["knee"],
        description=(
            "Crisp intervals combining squats, modified plank holds, and cardio bursts at home."
        ),
        steps=[
            WorkoutStep(
                id="high_knee_march",
                name="Dynamic High-Knee March",
                instructions=(
                    "Drive knees up briskly toward waist height with tight core and tall posture."
                ),
                duration_sec=45,
                rest_sec=15,
                muscle_groups=["core", "hip_flexors", "cardio"],
                contraindications=["knee"],
                easier_alternative_name="Low Ankle Steps",
                easier_alternative_instructions=(
                    "Keep steps low near the floor without high knee lift."
                ),
            ),
            WorkoutStep(
                id="bodyweight_squats",
                name="Controlled Bodyweight Squats",
                instructions=(
                    "Push hips back as if sitting on a chair, keep chest proud, and press heels."
                ),
                duration_sec=45,
                rest_sec=20,
                muscle_groups=["quads", "glutes"],
                contraindications=["knee"],
                easier_alternative_name="Chair Sit-to-Stand",
                easier_alternative_instructions=(
                    "Touch a sturdy dining chair lightly on every squat before standing."
                ),
            ),
            WorkoutStep(
                id="incline_pushups",
                name="Counter / Sofa Incline Push-ups",
                instructions=(
                    "Place hands on a sturdy table or sofa edge, keep body straight, and lower "
                    "slowly."
                ),
                duration_sec=40,
                rest_sec=20,
                muscle_groups=["chest", "triceps", "core"],
                easier_alternative_name="Wall Push-ups",
                easier_alternative_instructions=(
                    "Press gently against a flat wall instead of an incline."
                ),
            ),
            WorkoutStep(
                id="standing_oblique_crunch",
                name="Standing Side Oblique Crunches",
                instructions=(
                    "Fingertips lightly behind ears, lift knee slightly toward same-side elbow "
                    "with straight back."
                ),
                duration_sec=45,
                rest_sec=15,
                muscle_groups=["obliques", "core"],
                easier_alternative_name="Standing Side Reach Stretch",
                easier_alternative_instructions=(
                    "Keep both feet planted and gently slide one hand down your thigh."
                ),
            ),
            WorkoutStep(
                id="calf_stretch_cooldown",
                name="Standing Calf & Hamstring Cooldown",
                instructions=(
                    "Step one foot back, press heel into floor, hold gently while catching breath."
                ),
                duration_sec=60,
                rest_sec=0,
                muscle_groups=["calves", "hamstrings"],
                easier_alternative_name="Seated Ankle Circles",
                easier_alternative_instructions=(
                    "Sit comfortably and roll ankles slowly in both directions."
                ),
            ),
        ],
    ),
    WorkoutRoutine(
        id="joint_friendly_mobility",
        name="Knee & Back-Safe Gentle Mobility",
        urdu_subtitle="Ghar ya office ke liye dard-se-paak halka stretch aur walk",
        workout_type=WorkoutCategory.FITNESS,
        level=DifficultyLevel.BEGINNER,
        duration_minutes=12,
        met_value=2.8,
        focus_areas=["joint_safety", "posture", "flexibility"],
        contraindications=[],
        description=(
            "Zero jumping, zero deep knee bending — ideal for beginners, sore joints, or post-meal "
            "movement."
        ),
        steps=[
            WorkoutStep(
                id="shoulder_rolls",
                name="Slow Shoulder & Chest Rolls",
                instructions=(
                    "Roll shoulders up, back, and down in smooth wide circles to ease tension."
                ),
                duration_sec=45,
                rest_sec=10,
                muscle_groups=["shoulders", "upper_back"],
                easier_alternative_name="Seated Shoulder Shrugs",
                easier_alternative_instructions=(
                    "Gently lift shoulders toward ears and relax down slowly."
                ),
            ),
            WorkoutStep(
                id="seated_cat_cow",
                name="Seated Spinal Cat-Cow Stretch",
                instructions=(
                    "Sit tall on a chair edge, open chest on inhale and round upper back softly "
                    "on exhale."
                ),
                duration_sec=50,
                rest_sec=15,
                muscle_groups=["spine", "posture"],
                easier_alternative_name="Gentle Upright Chest Openers",
                easier_alternative_instructions=(
                    "Clasp hands lightly near lower back and breathe into the chest."
                ),
            ),
            WorkoutStep(
                id="gentle_room_walk",
                name="Easy Flat-Foot Walk",
                instructions=(
                    "Walk calmly around the room with relaxed shoulders and smooth heel-to-toe "
                    "steps."
                ),
                duration_sec=60,
                rest_sec=15,
                muscle_groups=["legs", "digestion"],
                easier_alternative_name="Slow Seated Heel Raises",
                easier_alternative_instructions=(
                    "Lift heels gently while seated to stimulate leg circulation."
                ),
            ),
            WorkoutStep(
                id="standing_hamstring_hinge",
                name="Supported Chair Calf Stretch",
                instructions=(
                    "Hold a chair back, keep knees soft, and stretch one calf gently for 25s "
                    "per side."
                ),
                duration_sec=50,
                rest_sec=10,
                muscle_groups=["calves", "ankles"],
                easier_alternative_name="Point & Flex Foot Stretch",
                easier_alternative_instructions=(
                    "Point toes forward then pull back softly while seated."
                ),
            ),
            WorkoutStep(
                id="posture_reset",
                name="Mindful Posture & Breath Reset",
                instructions="Stack ears over shoulders, soften jaw, and take 5 long calm breaths.",
                duration_sec=45,
                rest_sec=0,
                muscle_groups=["posture", "relaxation"],
                easier_alternative_name="Natural Slow Breathing",
                easier_alternative_instructions=(
                    "Rest hands over stomach and notice each steady breath."
                ),
            ),
        ],
    ),
    WorkoutRoutine(
        id="face_yoga_jawline_chin",
        name="Jawline Sculpt & Double-Chin Toner",
        urdu_subtitle="Chehre aur jawline ki natural toning — rozana 8 minute",
        workout_type=WorkoutCategory.FACE_YOGA,
        level=DifficultyLevel.BEGINNER,
        duration_minutes=8,
        met_value=1.8,
        focus_areas=["jawline", "double_chin", "neck_toning"],
        contraindications=["neck"],
        description=(
            "Targeted gentle isometric holds to tone under-chin muscles and lift "
            "lower-face contour."
        ),
        steps=[
            WorkoutStep(
                id="jaw_warmup_massage",
                name="Warm-up Jawline Sweeps",
                instructions=(
                    "With clean hands and moisturizer, glide knuckles softly from chin toward "
                    "earlobes."
                ),
                duration_sec=45,
                rest_sec=10,
                muscle_groups=["jawline", "lymphatic"],
                easier_alternative_name="Light Fingertip Tapping",
                easier_alternative_instructions=(
                    "Tap fingertips lightly along the jawline for 30 to 45 seconds."
                ),
            ),
            WorkoutStep(
                id="chin_sky_lift",
                name="Skyward Chin Press",
                instructions=(
                    "Tilt chin slightly upward without neck strain, press tongue flat to roof "
                    "of mouth."
                ),
                duration_sec=40,
                rest_sec=15,
                muscle_groups=["submental", "neck_front"],
                contraindications=["neck"],
                easier_alternative_name="Neutral Tongue Roof Press",
                easier_alternative_instructions=(
                    "Keep head completely level looking straight ahead and press tongue gently."
                ),
            ),
            WorkoutStep(
                id="vowel_oo_ee",
                name="Exaggerated O-E Articulation",
                instructions=(
                    "Form a smooth wide 'O' then lift cheeks into a relaxed 'E' keeping forehead "
                    "calm."
                ),
                duration_sec=45,
                rest_sec=15,
                muscle_groups=["cheeks", "jaw", "mouth"],
                easier_alternative_name="Soft Half-Smile Holds",
                easier_alternative_instructions=(
                    "Hold a relaxed closed-lip smile gently for 5 seconds, rest 3 seconds."
                ),
            ),
            WorkoutStep(
                id="neck_drain_finish",
                name="Lymphatic Collarbone Glide",
                instructions=(
                    "Stroke palms downward softly from behind ears down neck sides to collarbone."
                ),
                duration_sec=45,
                rest_sec=0,
                muscle_groups=["lymphatic", "neck"],
                easier_alternative_name="Collarbone Breathing",
                easier_alternative_instructions=(
                    "Rest warm palms lightly over collarbones and breathe deeply."
                ),
            ),
        ],
    ),
    WorkoutRoutine(
        id="face_yoga_cheek_depuff",
        name="Morning De-Puff & Cheek Glow Flow",
        urdu_subtitle="Subah ki sujan kam karne aur natural glow ke liye gentle routine",
        workout_type=WorkoutCategory.FACE_YOGA,
        level=DifficultyLevel.BEGINNER,
        duration_minutes=7,
        met_value=1.6,
        focus_areas=["de_puff", "cheeks", "under_eye"],
        contraindications=[],
        description=(
            "Zero neck strain — gentle lymphatic drainage and cheek lift ideal right after washing "
            "your face."
        ),
        steps=[
            WorkoutStep(
                id="cheek_puff_pass",
                name="Air Cheek Swish",
                instructions=(
                    "Fill both cheeks with air and pass air smoothly left to right without strain."
                ),
                duration_sec=40,
                rest_sec=10,
                muscle_groups=["cheeks", "buccinator"],
                easier_alternative_name="Tiny Soft Cheek Inflate",
                easier_alternative_instructions=(
                    "Hold light air in cheeks for 5 seconds at a time without tension."
                ),
            ),
            WorkoutStep(
                id="temple_eye_sweep",
                name="Soft Under-Eye Ring-Finger Sweep",
                instructions=(
                    "Using ring fingers only, glide ultra-gently from inner under-eye to temples."
                ),
                duration_sec=45,
                rest_sec=10,
                muscle_groups=["orbicularis_oculi", "lymphatic"],
                easier_alternative_name="Warm Palm Eye Cupping",
                easier_alternative_instructions=(
                    "Rub hands together to warm palms and cup softly over closed eyes."
                ),
            ),
            WorkoutStep(
                id="cheekbone_lift",
                name="Gentle Cheekbone Smile Lift",
                instructions=(
                    "Lift mouth corners toward upper cheekbones gently while keeping "
                    "forehead smooth."
                ),
                duration_sec=40,
                rest_sec=15,
                muscle_groups=["zygomatic", "mid_face"],
                easier_alternative_name="Relaxed Facial Unclench",
                easier_alternative_instructions=(
                    "Drop lower jaw slightly and breathe out softly through parted lips."
                ),
            ),
            WorkoutStep(
                id="brow_smooth_finish",
                name="Forehead & Temple Release",
                instructions=(
                    "Sweep fingertips gently from center forehead outward toward temples cleanly."
                ),
                duration_sec=45,
                rest_sec=0,
                muscle_groups=["frontalis", "temples"],
                easier_alternative_name="Slow Temple Circles",
                easier_alternative_instructions=(
                    "Trace tiny gentle circles at temples with fingertips."
                ),
            ),
        ],
    ),
    WorkoutRoutine(
        id="face_yoga_neck_relax",
        name="Tech-Neck & Jaw Tension Release",
        urdu_subtitle="Screen use aur stress ki wajah se jaw/neck tightness khatam karein",
        workout_type=WorkoutCategory.FACE_YOGA,
        level=DifficultyLevel.BEGINNER,
        duration_minutes=6,
        met_value=1.5,
        focus_areas=["jaw_tension", "neck_release", "relaxation"],
        contraindications=["neck"],
        description=(
            "Calming evening routine to unclench the jaw and unwind face/neck muscles before sleep."
        ),
        steps=[
            WorkoutStep(
                id="jaw_hinge_massage",
                name="TMJ Jaw Hinge Circles",
                instructions=(
                    "Find the soft hinge in front of each ear and trace small soothing circles."
                ),
                duration_sec=45,
                rest_sec=10,
                muscle_groups=["masseter", "jaw"],
                easier_alternative_name="Warm Finger Hold",
                easier_alternative_instructions=(
                    "Rest warm fingertips gently on cheeks without circular pressure."
                ),
            ),
            WorkoutStep(
                id="chin_tucks",
                name="Gentle Level Chin Tucks",
                instructions=(
                    "Keep eyes level and slide chin straight back slightly for a gentle 3s hold."
                ),
                duration_sec=40,
                rest_sec=15,
                muscle_groups=["deep_neck_flexors", "posture"],
                contraindications=["neck"],
                easier_alternative_name="Shoulder Blade Gently Back",
                easier_alternative_instructions=(
                    "Keep head neutral and draw shoulder blades gently down away from ears."
                ),
            ),
            WorkoutStep(
                id="lion_exhale",
                name="Tension-Release Sigh Breath",
                instructions=(
                    "Inhale slowly through the nose, open mouth gently, exhale with a soft sigh."
                ),
                duration_sec=40,
                rest_sec=10,
                muscle_groups=["jaw", "face", "nervous_system"],
                easier_alternative_name="Soft Nose Exhale",
                easier_alternative_instructions=(
                    "Keep lips relaxed together and lengthen your exhale slowly."
                ),
            ),
            WorkoutStep(
                id="ear_jaw_glide",
                name="Ear-to-Collarbone Cooling Glide",
                instructions=(
                    "Finish with feather-light downward strokes so facial muscles relax fully."
                ),
                duration_sec=45,
                rest_sec=0,
                muscle_groups=["lymphatic", "relaxation"],
                easier_alternative_name="Eyes-Closed Deep Breath",
                easier_alternative_instructions=(
                    "Close eyes for 30 seconds and relax eyebrows and tongue."
                ),
            ),
        ],
    ),
)

_ROUTINES_BY_ID: dict[str, WorkoutRoutine] = {r.id: r for r in WORKOUT_ROUTINES}


def list_routines(
    *,
    workout_type: WorkoutCategory | None = None,
    exclude_contraindications: list[str] | None = None,
) -> list[WorkoutRoutine]:
    """Return workout/face-yoga routines filtered by category and joint safety tags."""
    avoid = {tag.strip().lower() for tag in (exclude_contraindications or []) if tag.strip()}
    results: list[WorkoutRoutine] = []
    for routine in WORKOUT_ROUTINES:
        if workout_type is not None and routine.workout_type != workout_type:
            continue
        routine_flags = {flag.lower() for flag in routine.contraindications}
        if avoid & routine_flags:
            continue
        results.append(routine)
    return results


def get_routine_by_id(routine_id: str) -> WorkoutRoutine | None:
    """Look up a curated workout or face yoga routine by its ID."""
    return _ROUTINES_BY_ID.get(routine_id.strip())
