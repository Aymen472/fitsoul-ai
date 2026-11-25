"""Deterministic input and output safety guardrails (English + Roman Urdu)."""

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.nutrition import FEMALE_CALORIE_FLOOR, get_calorie_floor
from app.models import UserProfile

MIN_BLOOD_SUGAR_MG_DL = 60
MAX_BLOOD_SUGAR_MG_DL = 350


class SafetyCategory(StrEnum):
    """Classification for safety guardrail checks."""

    SAFE = "safe"
    SELF_HARM = "self_harm"
    MEDICAL_EMERGENCY = "medical_emergency"
    EATING_DISORDER = "eating_disorder"
    PRESCRIPTION_MEDICINE = "prescription_medicine"
    EXTREME_DIET = "extreme_diet"


class InputSafetyResult(BaseModel):
    """Result of deterministic safety screening on a user message."""

    is_safe: bool
    category: SafetyCategory
    flagged_safety: bool = False
    stop_diet_advice: bool = False
    safe_response: str | None = None
    matched_rule: str | None = None


class OutputSafetyResult(BaseModel):
    """Result of deterministic safety verification on an AI-generated reply."""

    is_safe: bool
    violations: list[str] = Field(default_factory=list)
    sanitized_response: str


SELF_HARM_RESPONSE = (
    "Aap ki zindagi aur sehat sab se zyada qeemti hai. Main abhi diet ya weight ki koi advice "
    "nahi dunga — please is waqt akelay na rahein aur kisi qareebi dost, family member, ya "
    "doctor/counselor se baat karein.\n"
    "Pakistan mein aap free aur confidential madad ke liye **Umang Helpline (0311-7786264)** par "
    "rabta kar sakte hain, ya emergency mein **Rescue 1122** par call karein. Agar aap Pakistan "
    "se bahar hain to apne local emergency number ya crisis helpline par foran rabta karein."
)

MEDICAL_EMERGENCY_RESPONSE = (
    "Yeh symptoms urgent medical attention maangte hain. Main abhi diet guidance rok raha hoon — "
    "please foran **nearest hospital emergency** jayein ya **Rescue 1122** (ya apne local "
    "emergency number) par call karein aur doctor se check karwayein."
)

EATING_DISORDER_RESPONSE = (
    "Main samajh sakta hoon ke yeh feelings aur body pressure bohat mushkil ho sakte hain, aur "
    "main aap ko bilkul judge nahi kar raha. Is waqt hum calorie deficit ya dieting rok rahe "
    "hain kyunki aap ki physical aur mental health sab se pehle aati hai.\n"
    "Please kisi qualified doctor, therapist, ya registered clinical dietitian se baat karein — "
    "aur Pakistan mein emotional support ke liye **Umang Helpline (0311-7786264)** par bhi "
    "rabta kiya ja sakta hai."
)

PRESCRIPTION_MEDICINE_RESPONSE = (
    "FitSoul AI ek lifestyle aur nutrition companion hai — main koi **prescription medicine, "
    "injection, ya dosage** suggest ya prescribe nahi kar sakta. Kisi bhi dawai (jaise Metformin, "
    "Ozempic, Thyroxine, ya blood pressure meds) ke liye please apne qualified doctor se mashwara "
    "karein."
)

EXTREME_DIET_RESPONSE = (
    "Itni kam calories ya bohot tez weight-loss tareeqay (crash dieting / water fasting) aap ki "
    "health, hormones aur metabolism ke liye dangerous ho sakte hain. FitSoul AI kabhi female "
    "ke liye **1200 kcal** aur male ke liye **1500 kcal** se neeche ka plan nahi deta.\n"
    "Sustainable aur safe pace **0.5%–1% body weight per week** hai — hum isi safe target ke "
    "mutabiq aap ke liye desi, filling meal plan bana sakte hain."
)

SAFE_OUTPUT_FALLBACK = (
    "Maaf kijiye, main is tarah ki medical ya unsafe diet advice nahi de sakta. FitSoul AI hamesha "
    "safe calorie floors (female ≥ 1200 kcal, male ≥ 1500 kcal) follow karta hai aur koi "
    "prescription medicine ya dosage suggest nahi karta. Kisi bhi medical mashware ke liye "
    "please apne doctor se rabta karein."
)

_SELF_HARM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bsuicid(?:e|al)\b",
        r"\bkill myself\b",
        r"\bend my life\b",
        r"\bwant to die\b",
        r"\bdon'?t want to live\b",
        r"\bdo not want to live\b",
        r"\bhurt myself\b",
        r"\bself[- ]?harm\b",
        r"\bcut(?:ting)? myself\b",
        r"\btake my (?:own )?life\b",
        r"\boverdose\b",
        r"\bkhud\s*kushi\b",
        r"\bmarna chaht[aei]\b",
        r"\bmar jaa?[ou]n\b",
        r"\bjeena nahi\b",
        r"\bzindagi khatam\b",
        r"\bzeher kha\b",
        r"\bapne aap ko nuksan\b",
    )
)

_EMERGENCY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bchest pain\b",
        r"\bseene mei?n dard\b",
        r"\bcan'?t breathe\b",
        r"\bcannot breathe\b",
        r"\bdifficulty breathing\b",
        r"\bsaans nahi aa rah[aei]\b",
        r"\bsaans phool rah[aei]\b",
        r"\bfaint(?:ing|ed)?\b",
        r"\bpassed out\b",
        r"\bbehosh\b",
        r"\bvomiting blood\b",
        r"\bkhoon ki ulti\b",
        r"\bheart attack\b",
        r"\bstroke\b",
        r"\bchakkar aur behosh",
    )
)

_BLOOD_SUGAR_VALUE_RE = re.compile(
    r"\b(?:blood sugar|sugar level|glucose|sugar)\b[^0-9]{0,18}(\d{2,3})\b",
    re.IGNORECASE,
)

_EATING_DISORDER_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:throw(?:ing)? up|threw up|vomit(?:ing)?)\b.*\b(?:eat(?:ing)?|food|meal|khana)\b",
        r"\b(?:khane ke baad|khana kha kar)\b.*\bulti\b",
        r"\bulti kar k[ey]\b",
        r"\binduce vomiting\b",
        r"\bmake myself vomit\b",
        r"\bfingers? down my throat\b",
        r"\bpurg(?:e|ing)\b",
        r"\bbinge and purge\b",
        r"\bchew and spit\b",
        r"\blaxatives?\b.*(?:weight|lose|diet|thin|slim|patla|after eat)",
        r"\banorexi(?:a|c)\b",
        r"\bbulimi(?:a|c)\b",
        r"\bstarv(?:e|ing) myself\b",
        r"\bbhook[aei] reh kar\b",
        r"\b(?:zero|0)\s*calor(?:ie|ies)\s*(?:diet|plan)?\b",
        r"\b(?:don'?t|do not|won'?t|stop) eat(?:ing)?\s*(?:for days|at all|completely)\b",
        r"\bkhana bilkul chh?or\b",
        r"\bhate my body\b.*\b(?:won'?t eat|starve)\b",
    )
)

_PRESCRIPTION_DRUG_RE = re.compile(
    r"\b(?:"
    r"metformin|glucophage|ozempic|wegovy|mounjaro|saxenda|semaglutide|tirzepatide|"
    r"orlistat|xenical|phentermine|levothyroxine|thyroxine|eltroxin|insulin|"
    r"glimepiride|sitagliptin|amlodipine|losartan|spironolactone|clomid|letrozole|"
    r"sibutramine|fat burner (?:pill|pills|tablet|tablets|capsule|capsules)|"
    r"weight[- ]loss (?:pill|pills|tablet|tablets|injection|drip)|"
    r"slimming (?:pill|pills|tablet|tablets|drip)"
    r")\b",
    re.IGNORECASE,
)

_PRESCRIPTION_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bkitni\s*(?:mg|goli|goliyan|tablets?)\b",
        r"\b(?:dosage|dose)\s+(?:of|for)\b",
        r"\bprescribe\b",
        r"\b(?:kaun|kon)\s*si\s*dawai\b",
        r"\bdawai\s+(?:bata|suggest|likh)\b",
        r"\b(?:medicine|medication|tablet)\s+(?:for|to lose|for pcos|for diabetes|for weight)\b",
    )
)

_DAILY_CALORIE_RE = re.compile(
    r"(?:"
    r"(?:only|sirf|just|eat|eating|plan|diet|daily|per day|a day|roz|rozana|target|keep)"
    r"\D{0,20}(\d{2,4})\s*(?:kcal|k?cal(?:ories?)?)\b"
    r"|"
    r"\b(\d{2,4})\s*(?:kcal|k?cal(?:ories?)?)\s*"
    r"(?:ka plan|diet|plan|per day|a day|daily|only|sirf|roz|me|mein)"
    r")",
    re.IGNORECASE,
)

_MEAL_CONTEXT_RE = re.compile(
    r"\b(?:breakfast|lunch|dinner|snack|nashta|iftar|sehri|roti|serving|bowl|plate)\b",
    re.IGNORECASE,
)

_RAPID_LOSS_WEEK_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b.{0,28}\b(?:1\s*week|a\s*week|1\s*haft[ae]|"
    r"ek\s*haft[ae]|per\s*week|in\s*(?:[1-7])\s*(?:days?|din))\b"
    r"|"
    r"\b(?:1\s*week|a\s*week|1\s*haft[ae]|ek\s*haft[ae]|in\s*(?:[1-7])\s*(?:days?|din))"
    r"\b.{0,28}\b(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b",
    re.IGNORECASE,
)

_RAPID_LOSS_TWO_WEEKS_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b.{0,28}\b(?:2\s*weeks?|2\s*haft[ae]|do\s*haft[ae])\b"
    r"|"
    r"\b(?:2\s*weeks?|2\s*haft[ae]|do\s*haft[ae])\b.{0,28}\b(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b",
    re.IGNORECASE,
)

_RAPID_LOSS_MONTH_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b.{0,28}\b(?:1\s*month|a\s*month|1\s*mahin[ae]|"
    r"ek\s*mahin[ae]|30\s*(?:days?|din))\b"
    r"|"
    r"\b(?:1\s*month|a\s*month|1\s*mahin[ae]|ek\s*mahin[ae]|30\s*(?:days?|din))"
    r"\b.{0,28}\b(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b",
    re.IGNORECASE,
)

_EXTREME_FASTING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:water|dry)\s*fast(?:ing)?\b",
        r"\bsirf\s+paa?ni\s+(?:pee|pe|pi)\b",
        r"\bonly\s+water\s+for\b",
        r"\b([2-9]|\d{2,})\s*[- ]?(?:day|din)\s*(?:water\s*)?fast\b",
        r"\bskip\s+all\s+meals\b",
        r"\bkhana\s+bilkul\s+band\b",
        r"\bcrash\s+diet\b",
        r"\beat\s+nothing\b",
    )
)

_OUTPUT_DOSAGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:take|use|start)\s+\d+(?:\.\d+)?\s*(?:mg|mcg)\b",
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg)\s*(?:tablet|pill|capsule|dose|daily|twice|once)\b",
        r"\b\d+\s*(?:tablets?|pills?|capsules?|goli|goliyan)\s*(?:daily|a day|per day|rozana)\b",
        r"\brozana\s+\d+\s*(?:goli|goliyan|tablet)\b",
    )
)


def _match_any(patterns: tuple[re.Pattern[str], ...], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match is not None:
            return match.group(0)
    return None


def _find_subfloor_calorie_violation(text: str, floor: int) -> str | None:
    for match in _DAILY_CALORIE_RE.finditer(text):
        snippet = match.group(0)
        if _MEAL_CONTEXT_RE.search(snippet):
            continue
        raw_num = match.group(1) or match.group(2)
        if raw_num is not None and int(raw_num) < floor:
            return raw_num
    return None


def _check_extreme_diet(message: str, floor: int) -> str | None:
    if fast_match := _match_any(_EXTREME_FASTING_PATTERNS, message):
        return fast_match

    if subfloor := _find_subfloor_calorie_violation(message, floor):
        return f"{subfloor} kcal"

    if match := _RAPID_LOSS_WEEK_RE.search(message):
        kg = float(match.group(1) or match.group(2))
        if kg >= 3.0:
            return match.group(0)

    if match := _RAPID_LOSS_TWO_WEEKS_RE.search(message):
        kg = float(match.group(1) or match.group(2))
        if kg >= 5.0:
            return match.group(0)

    if match := _RAPID_LOSS_MONTH_RE.search(message):
        kg = float(match.group(1) or match.group(2))
        if kg >= 8.0:
            return match.group(0)

    return None


def check_input_safety(
    message: str,
    profile: UserProfile | None = None,
) -> InputSafetyResult:
    """Screen a user message for self-harm, medical crisis, ED, medicine, or crash-diet risks."""
    text = message.strip()
    if not text:
        return InputSafetyResult(is_safe=True, category=SafetyCategory.SAFE)

    if matched := _match_any(_SELF_HARM_PATTERNS, text):
        return InputSafetyResult(
            is_safe=False,
            category=SafetyCategory.SELF_HARM,
            flagged_safety=True,
            stop_diet_advice=True,
            safe_response=SELF_HARM_RESPONSE,
            matched_rule=matched,
        )

    if matched := _match_any(_EMERGENCY_PATTERNS, text):
        return InputSafetyResult(
            is_safe=False,
            category=SafetyCategory.MEDICAL_EMERGENCY,
            flagged_safety=True,
            stop_diet_advice=True,
            safe_response=MEDICAL_EMERGENCY_RESPONSE,
            matched_rule=matched,
        )

    if sugar_match := _BLOOD_SUGAR_VALUE_RE.search(text):
        sugar_val = int(sugar_match.group(1))
        if sugar_val <= MIN_BLOOD_SUGAR_MG_DL or sugar_val >= MAX_BLOOD_SUGAR_MG_DL:
            return InputSafetyResult(
                is_safe=False,
                category=SafetyCategory.MEDICAL_EMERGENCY,
                flagged_safety=True,
                stop_diet_advice=True,
                safe_response=MEDICAL_EMERGENCY_RESPONSE,
                matched_rule=sugar_match.group(0),
            )

    if matched := _match_any(_EATING_DISORDER_PATTERNS, text):
        return InputSafetyResult(
            is_safe=False,
            category=SafetyCategory.EATING_DISORDER,
            flagged_safety=True,
            stop_diet_advice=True,
            safe_response=EATING_DISORDER_RESPONSE,
            matched_rule=matched,
        )

    if med_match := _PRESCRIPTION_DRUG_RE.search(text):
        return InputSafetyResult(
            is_safe=False,
            category=SafetyCategory.PRESCRIPTION_MEDICINE,
            flagged_safety=False,
            stop_diet_advice=False,
            safe_response=PRESCRIPTION_MEDICINE_RESPONSE,
            matched_rule=med_match.group(0),
        )

    if matched := _match_any(_PRESCRIPTION_REQUEST_PATTERNS, text):
        return InputSafetyResult(
            is_safe=False,
            category=SafetyCategory.PRESCRIPTION_MEDICINE,
            flagged_safety=False,
            stop_diet_advice=False,
            safe_response=PRESCRIPTION_MEDICINE_RESPONSE,
            matched_rule=matched,
        )

    floor = get_calorie_floor(profile.gender) if profile is not None else FEMALE_CALORIE_FLOOR
    if extreme_match := _check_extreme_diet(text, floor):
        return InputSafetyResult(
            is_safe=False,
            category=SafetyCategory.EXTREME_DIET,
            flagged_safety=False,
            stop_diet_advice=False,
            safe_response=EXTREME_DIET_RESPONSE,
            matched_rule=extreme_match,
        )

    return InputSafetyResult(is_safe=True, category=SafetyCategory.SAFE)


def check_output_safety(
    response_text: str,
    profile: UserProfile | None = None,
) -> OutputSafetyResult:
    """Verify an AI-generated reply does not leak medicines, dosages, or sub-floor plans."""
    violations: list[str] = []

    if drug_match := _PRESCRIPTION_DRUG_RE.search(response_text):
        violations.append(f"Mentions restricted medicine/drug: '{drug_match.group(0)}'")

    if dosage_match := _match_any(_OUTPUT_DOSAGE_PATTERNS, response_text):
        violations.append(f"Contains medication dosage instruction: '{dosage_match}'")

    floor = get_calorie_floor(profile.gender) if profile is not None else FEMALE_CALORIE_FLOOR
    if subfloor := _find_subfloor_calorie_violation(response_text, floor):
        violations.append(
            f"Recommends daily calories ({subfloor} kcal) below safe floor ({floor} kcal)"
        )

    if fast_match := _match_any(_EXTREME_FASTING_PATTERNS, response_text):
        violations.append(f"Recommends extreme fasting or starvation: '{fast_match}'")

    if violations:
        return OutputSafetyResult(
            is_safe=False,
            violations=violations,
            sanitized_response=SAFE_OUTPUT_FALLBACK,
        )
    return OutputSafetyResult(
        is_safe=True,
        violations=[],
        sanitized_response=response_text,
    )
