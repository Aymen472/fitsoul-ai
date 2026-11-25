"""Whitelist-only OTC supplement information module with high-risk safety lockout."""

from pydantic import BaseModel, Field

from app.models import UserProfile

MANDATORY_DOCTOR_NOTE = (
    "Koi bhi supplement shuru karne se pehle apne doctor se zaroor confirm karein. "
    "FitSoul AI medical prescription ya dosage nahi deta."
)


class SupplementInfo(BaseModel):
    """Evidence-based general OTC supplement overview without prescription dosages."""

    id: str
    name: str
    relevant_conditions: list[str]
    general_info: str
    doctor_note: str = MANDATORY_DOCTOR_NOTE


class SupplementGuidanceResponse(BaseModel):
    """Response returned for supplement guidance queries."""

    allowed: bool
    disabled_reason: str | None = None
    supplements: list[SupplementInfo] = Field(default_factory=list)
    disclaimer: str = MANDATORY_DOCTOR_NOTE


SUPPLEMENT_WHITELIST: tuple[SupplementInfo, ...] = (
    SupplementInfo(
        id="inositol",
        name="Myo-Inositol",
        relevant_conditions=["pcos"],
        general_info=(
            "PCOS mein insulin sensitivity aur hormonal balance ki support ke liye commonly "
            "discuss kiya jata hai; pehle doctor se blood tests aur suitability confirm karein."
        ),
    ),
    SupplementInfo(
        id="vitamin_d",
        name="Vitamin D3",
        relevant_conditions=["general", "pcos", "hypothyroid"],
        general_info=(
            "South Asia mein Vitamin D ki kami bohat aam hai; bone, mood aur metabolic health "
            "ke liye doctor se 25-OH Vitamin D blood test check karwa kar mashwara lein."
        ),
    ),
    SupplementInfo(
        id="omega_3",
        name="Omega-3 Fatty Acids (Fish Oil / Algae Oil)",
        relevant_conditions=["general", "pcos", "hypertension"],
        general_info=(
            "Heart health aur triglycerides ko support karne mein madadgar ho sakta hai jab "
            "weekly oily fish intake kam ho."
        ),
    ),
    SupplementInfo(
        id="magnesium",
        name="Magnesium (Glycinate / Citrate)",
        relevant_conditions=["general", "pcos", "diabetes_t2"],
        general_info=(
            "Sleep quality, muscle recovery aur glucose metabolism ke liye general nutrition "
            "support ke tor par discuss kiya jata hai."
        ),
    ),
    SupplementInfo(
        id="vitamin_b12",
        name="Vitamin B12",
        relevant_conditions=["general", "veg", "diabetes_t2"],
        general_info=(
            "Energy aur nerve health ke liye zaroori hai, khaas tor par vegetarian diet "
            "follow karne walon ke liye."
        ),
    ),
)


def get_safe_supplement_info(
    profile: UserProfile,
    *,
    requested_name: str | None = None,
) -> SupplementGuidanceResponse:
    """Return whitelisted OTC supplement info, or disable completely for high-risk users."""
    if not profile.supplements_allowed:
        reasons = list(profile.high_risk_reasons)
        if profile.on_regular_medication:
            reasons.append("regular_medication")
        reason_label = ", ".join(reasons) if reasons else "medical_safety"
        return SupplementGuidanceResponse(
            allowed=False,
            disabled_reason=(
                f"Supplement suggestions are disabled for safety ({reason_label}). "
                "Please consult your doctor before taking any supplement."
            ),
            supplements=[],
            disclaimer=MANDATORY_DOCTOR_NOTE,
        )

    if requested_name is not None:
        query = requested_name.strip().lower()
        matches = [
            item
            for item in SUPPLEMENT_WHITELIST
            if query and (query in item.id.lower() or query in item.name.lower())
        ]
        return SupplementGuidanceResponse(
            allowed=True,
            supplements=matches,
            disclaimer=MANDATORY_DOCTOR_NOTE,
        )

    user_tags = {c.value for c in profile.conditions} | {profile.diet_type.value, "general"}
    prioritized = sorted(
        SUPPLEMENT_WHITELIST,
        key=lambda item: (
            -len((set(item.relevant_conditions) - {"general"}) & user_tags),
            item.id,
        ),
    )
    return SupplementGuidanceResponse(
        allowed=True,
        supplements=prioritized,
        disclaimer=MANDATORY_DOCTOR_NOTE,
    )
