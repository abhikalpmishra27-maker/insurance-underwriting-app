"""
==============================================================================
  AI-BASED AUTOMATED LIFE INSURANCE UNDERWRITING TOOL
  Built from: Proposal Form, Controlled Data Set, Assignment Overview
==============================================================================
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date, datetime


@dataclass
class ProposalForm:
    name: str
    gender: str
    dob: str
    place_of_residence: str
    profession: str
    height_cm: float
    weight_kg: float
    yearly_income: float
    source_of_income: str
    base_cover: float
    cir_cover: float
    accident_cover: float
    parent_health_status: str
    health_conditions: dict = field(default_factory=dict)
    habits: dict = field(default_factory=dict)
    risky_occupations: list = field(default_factory=list)


BMI_EMR_TABLE = [
    (float('-inf'), 18, +10),
    (19, 23, 0),
    (24, 28, +5),
    (29, 33, +10),
    (34, 38, +15),
    (38, float('inf'), +20),
]

FAMILY_HISTORY_EMR = {
    "both_above_65": -10,
    "one_above_65": -5,
    "both_below_65": +10,
}

HEALTH_EMR_TABLE = {
    "thyroid": [2.5, 5.0, 7.5, 10.0],
    "asthma": [5.0, 7.5, 10.0, 12.5],
    "hypertension": [5.0, 7.5, 10.0, 15.0],
    "diabetes": [10.0, 15.0, 20.0, 25.0],
    "gut_disorder": [5.0, 10.0, 15.0, 20.0],
}

COMORBIDITY_EXTRA = {2: +20, 3: +40}

HABIT_EMR_TABLE = {
    "smoking": {"occasionally": 5, "moderate": 10, "high": 15},
    "alcohol": {"occasionally": 5, "moderate": 10, "high": 15},
    "tobacco": {"occasionally": 5, "moderate": 10, "high": 15},
}

HABIT_COEXISTENCE_EXTRA = {2: +20, 3: +40}

OCCUPATION_EXTRA_PER_MILLE = {
    "athlete": 2, "pilot": 6, "driver": 2, "merchant_navy": 3, "oil_gas": 3,
}

LIFE_RATING_TABLE = [
    (20, 35, "I", 1), (40, 60, "II", 2), (65, 85, "III", 3),
    (90, 120, "IV", 4), (125, 170, "V", 6), (175, 225, "VI", 8),
    (230, 275, "VII", 10), (280, 350, "VIII", 12), (355, 450, "IX", 16),
    (455, 550, "X", 20),
]

CIR_RATING_TABLE = [
    (0, 20, "Std", None), (21, 35, "I", 1), (36, 60, "II", 2),
    (61, 75, "III", 3), (76, 100, "IV", 4),
]

PREMIUM_RATE_TABLE = {
    (18, 35): (1.5, 1.0, 3.0), (36, 40): (3.0, 1.0, 6.0),
    (41, 45): (4.5, 1.0, 12.0), (46, 50): (6.0, 1.0, 15.0),
    (51, 55): (7.5, 1.5, 20.0), (56, 60): (9.0, 1.5, 25.0),
    (61, 65): (10.5, 1.5, None),
}

FINANCIAL_UW_TABLE = [
    (0, 35, 25), (36, 45, 20), (46, 50, 15), (51, 55, 15), (56, 999, 10),
]


def calculate_age(dob_str: str) -> int:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d %b %Y", "%d %b %y",
                "%d-%m-%Y", "%d-%m-%y", "%d %B %Y", "%Y-%m-%d"):
        try:
            dob = datetime.strptime(dob_str.strip(), fmt).date()
            today = date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date of birth: '{dob_str}'. Use DD/MM/YYYY or YYYY-MM-DD.")


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100
    return round(weight_kg / (height_m ** 2), 1)


def get_bmi_emr(bmi: float) -> int:
    for low, high, emr in BMI_EMR_TABLE:
        if low <= bmi <= high:
            return emr
    return +20


def get_premium_rate(age: int):
    for (low, high), rates in PREMIUM_RATE_TABLE.items():
        if low <= age <= high:
            return rates
    return None


def get_life_rating(emr_total: float):
    for low, high, cls, factor in LIFE_RATING_TABLE:
        if low <= emr_total <= high:
            return cls, factor
    return None, None


def get_cir_rating(emr_total: float):
    for low, high, cls, factor in CIR_RATING_TABLE:
        if low <= emr_total <= high:
            return cls, factor
    return None, None


def get_max_cover_multiple(age: int) -> int:
    for low, high, multiple in FINANCIAL_UW_TABLE:
        if low <= age <= high:
            return multiple
    return 10


def check_edge_cases(proposal, age, bmi, total_emr, active_conditions, active_habits):
    flags = []
    if age < 18:
        flags.append(("DECLINE", "AGE_MINOR", f"Applicant is {age} years old — below minimum insurable age of 18."))
    elif age > 65:
        flags.append(("DECLINE", "AGE_LIMIT", f"Applicant is {age} years old — above maximum insurable age of 65."))
    elif age > 60:
        flags.append(("WARNING", "CIR_AGE", "CIR not available for age > 60. CIR cover will be declined."))
    if bmi < 18:
        flags.append(("MANUAL_UW", "BMI_UNDERWEIGHT", f"BMI {bmi} is below 18 (underweight) — requires manual assessment."))
    if bmi > 38:
        flags.append(("MANUAL_UW", "BMI_SEVERE_OBESE", f"BMI {bmi} exceeds 38 (severe obesity) — not in standard table, requires manual assessment."))
    if len(active_conditions) >= 4:
        flags.append(("MANUAL_UW", "EXCESS_COMORBID", f"{len(active_conditions)} active health conditions detected. Co-morbidity table covers max 3. Manual underwriting required."))
    for cond, sev in proposal.health_conditions.items():
        if sev == 4:
            flags.append(("MANUAL_UW", f"SEV4_{cond.upper()}", f"{cond.title()} at Severity Level 4 (very high dose medication) — likely requires medical officer review."))
    high_habits = [h for h, freq in proposal.habits.items() if freq == "high"]
    if len(high_habits) == 3:
        flags.append(("MANUAL_UW", "ALL_HABITS_HIGH", "All 3 personal habits (smoking/alcohol/tobacco) at high dose — requires manual underwriting."))
    if total_emr < 20:
        flags.append(("INFO", "EMR_BELOW_TABLE", f"Total EMR {total_emr} is below the rating table minimum of 20. Standard acceptance applies."))
    if total_emr > 550:
        flags.append(("DECLINE", "EMR_EXCEEDS_MAX", f"Total EMR {total_emr} exceeds maximum ratable EMR of 550. Policy must be declined."))
    elif total_emr > 450:
        flags.append(("MANUAL_UW", "EMR_VERY_HIGH", f"Total EMR {total_emr} falls in Class X (highest risk band). Senior actuary sign-off required."))
    max_multiple = get_max_cover_multiple(age)
    max_allowed = proposal.yearly_income * max_multiple
    if proposal.base_cover > max_allowed:
        flags.append(("MANUAL_UW", "FINANCIAL_UW_LIFE", f"Base cover requested ({proposal.base_cover:,.0f}) exceeds financial UW limit ({max_allowed:,.0f} = {max_multiple}x income) for age {age}."))
    if proposal.cir_cover > max_allowed:
        flags.append(("MANUAL_UW", "FINANCIAL_UW_CIR", f"CIR cover requested ({proposal.cir_cover:,.0f}) exceeds financial UW limit."))
    if proposal.accident_cover > max_allowed:
        flags.append(("MANUAL_UW", "FINANCIAL_UW_ACCIDENT", f"Accident cover requested ({proposal.accident_cover:,.0f}) exceeds financial UW limit."))
    if proposal.source_of_income.lower() not in ("salary", "business", "profession", "self-employed"):
        flags.append(("WARNING", "INCOME_SOURCE", f"Income source '{proposal.source_of_income}' is non-standard — verify income documents."))
    if len(proposal.risky_occupations) > 1:
        flags.append(("MANUAL_UW", "MULTI_OCCUPATION", f"Multiple risky occupations declared: {proposal.risky_occupations}. Manual review required."))
    if proposal.gender.lower() not in ("male", "female"):
        flags.append(("WARNING", "GENDER_UNKNOWN", f"Gender '{proposal.gender}' not recognized. Expected Male/Female."))
    return flags


def underwrite(proposal: ProposalForm) -> dict:
    report = {}
    report["applicant"] = proposal.name
    age = calculate_age(proposal.dob)
    bmi = calculate_bmi(proposal.weight_kg, proposal.height_cm)
    report["age"] = age
    report["bmi"] = bmi
    emr_bmi = get_bmi_emr(bmi)
    report["emr_bmi"] = emr_bmi
    emr_family = FAMILY_HISTORY_EMR.get(proposal.parent_health_status, 0)
    report["emr_family"] = emr_family
    emr_health_breakdown = {}
    active_conditions = []
    for condition, severity in proposal.health_conditions.items():
        if severity and severity > 0:
            condition_key = condition.lower().replace(" ", "_")
            sev_idx = int(severity) - 1
            if condition_key in HEALTH_EMR_TABLE and 0 <= sev_idx < 4:
                pts = HEALTH_EMR_TABLE[condition_key][sev_idx]
                emr_health_breakdown[condition] = pts
                active_conditions.append(condition)
            else:
                emr_health_breakdown[condition] = 0
    emr_health_raw = sum(emr_health_breakdown.values())
    n_conditions = len(active_conditions)
    comorbidity_extra = 0
    if n_conditions >= 2:
        comorbidity_extra = COMORBIDITY_EXTRA.get(min(n_conditions, 3), 40)
    emr_health_total = emr_health_raw + comorbidity_extra
    report["emr_health_breakdown"] = emr_health_breakdown
    report["emr_comorbidity_extra"] = comorbidity_extra
    report["emr_health_total"] = emr_health_total
    report["active_conditions"] = active_conditions
    emr_habits_breakdown = {}
    active_habits = []
    for habit, freq in proposal.habits.items():
        if freq and freq.lower() not in ("no", "none", ""):
            freq_key = freq.lower()
            pts = HABIT_EMR_TABLE.get(habit.lower(), {}).get(freq_key, 0)
            emr_habits_breakdown[habit] = pts
            if pts > 0:
                active_habits.append(habit)
    emr_habits_raw = sum(emr_habits_breakdown.values())
    n_habits = len(active_habits)
    habit_extra = 0
    if n_habits >= 2:
        habit_extra = HABIT_COEXISTENCE_EXTRA.get(min(n_habits, 3), 40)
    emr_habits_total = emr_habits_raw + habit_extra
    report["emr_habits_breakdown"] = emr_habits_breakdown
    report["emr_habit_coexistence_extra"] = habit_extra
    report["emr_habits_total"] = emr_habits_total
    report["active_habits"] = active_habits
    total_emr = emr_bmi + emr_family + emr_health_total + emr_habits_total
    report["total_emr"] = total_emr
    life_class, life_factor = get_life_rating(total_emr)
    cir_class, cir_factor = get_cir_rating(total_emr)
    report["life_rating_class"] = life_class
    report["life_rating_factor"] = life_factor
    report["cir_rating_class"] = cir_class
    report["cir_rating_factor"] = cir_factor
    if total_emr > 550:
        uw_decision = "DECLINE"
    elif total_emr > 275:
        uw_decision = "ACCEPTANCE WITH LOADING — Senior Actuary Sign-off Required"
    elif life_class:
        uw_decision = "ACCEPTANCE WITH LOADING"
    else:
        uw_decision = "STANDARD ACCEPTANCE"
    report["uw_decision"] = uw_decision
    flags = check_edge_cases(proposal, age, bmi, total_emr, active_conditions, active_habits)
    report["flags"] = flags
    rates = get_premium_rate(age)
    premium_detail = {}
    if rates is None:
        premium_detail["error"] = f"Age {age} is outside insurable age range (18–65)."
        report["premium"] = premium_detail
        return report
    life_rate, acc_rate, cir_rate = rates
    life_base_premium = (life_rate * proposal.base_cover) / 1000
    life_loading_pct = 0.25 * (life_factor if life_factor else 0)
    life_loading_amt = life_loading_pct * life_base_premium
    occ_extra_per_mille = sum(OCCUPATION_EXTRA_PER_MILLE.get(occ, 0) for occ in proposal.risky_occupations)
    life_occ_extra = (occ_extra_per_mille * proposal.base_cover) / 1000
    life_total_premium = life_base_premium + life_loading_amt + life_occ_extra
    premium_detail["life"] = {
        "sum_assured": proposal.base_cover,
        "base_rate_per_mille": life_rate,
        "base_premium": round(life_base_premium, 2),
        "rating_class": life_class,
        "rating_factor": life_factor,
        "loading_pct": f"{life_loading_pct*100:.0f}%",
        "loading_amount": round(life_loading_amt, 2),
        "occ_extra_per_mille": occ_extra_per_mille,
        "occ_extra_amount": round(life_occ_extra, 2),
        "total_premium": round(life_total_premium, 2),
    }
    acc_base_premium = (acc_rate * proposal.accident_cover) / 1000
    acc_occ_extra = (occ_extra_per_mille * proposal.accident_cover) / 1000
    acc_total_premium = acc_base_premium + acc_occ_extra
    premium_detail["accident_rider"] = {
        "sum_assured": proposal.accident_cover,
        "base_rate_per_mille": acc_rate,
        "base_premium": round(acc_base_premium, 2),
        "occ_extra_amount": round(acc_occ_extra, 2),
        "total_premium": round(acc_total_premium, 2),
    }
    cir_premium_detail = {}
    if age > 60:
        cir_premium_detail["status"] = "DECLINED — CIR not available above age 60"
    elif cir_class is None or total_emr > 100:
        cir_premium_detail["status"] = f"DECLINED — Total EMR {total_emr:.1f} exceeds CIR max ratable EMR of 100"
    else:
        cir_base_premium = (cir_rate * proposal.cir_cover) / 1000
        cir_loading_pct = 0.30 * (cir_factor if cir_factor else 0)
        cir_loading_amt = cir_loading_pct * cir_base_premium
        cir_total_premium = cir_base_premium + cir_loading_amt
        cir_premium_detail = {
            "sum_assured": proposal.cir_cover,
            "base_rate_per_mille": cir_rate,
            "base_premium": round(cir_base_premium, 2),
            "rating_class": cir_class,
            "rating_factor": cir_factor,
            "loading_pct": f"{cir_loading_pct*100:.0f}%",
            "loading_amount": round(cir_loading_amt, 2),
            "total_premium": round(cir_total_premium, 2),
        }
    premium_detail["cir"] = cir_premium_detail
    life_total = premium_detail["life"]["total_premium"]
    acc_total = premium_detail["accident_rider"]["total_premium"]
    cir_total = premium_detail["cir"].get("total_premium", 0)
    premium_detail["grand_total"] = round(life_total + acc_total + cir_total, 2)
    report["premium"] = premium_detail
    return report
