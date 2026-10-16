"""Deterministic, explainable evidence adjustments for possible causes.

The vision model ranks causes from the photos. Weather and satellite context then add or remove a
few bounded points per cause using published agronomic tendencies (e.g. late blight favours cool,
humid spells; spider mites favour hot, dry ones). Nothing here calls a model, so it is fast,
repeatable and testable; every adjustment carries the facts that produced it.
"""

from dataclasses import dataclass
from enum import StrEnum
from statistics import mean

from app.models.weather import RecentWeather
from app.schemas.satellite import SatelliteAnalysis, VegetationTrend
from app.schemas.triage import EvidenceContribution, EvidenceEffect, EvidenceSignal, WeatherFacts

WEATHER_MAX_POINTS = 10
SATELLITE_MAX_POINTS = 6

HUMID_DAY_RH = 80
WET_DAY_MM = 1.0
HOT_DAY_C = 35
COLD_NIGHT_C = 8


class Archetype(StrEnum):
    HUMID_DISEASE = "humid_disease"  # fungal leaf diseases: humidity + a temperature band
    SPLASH_DISEASE = "splash_disease"  # bacterial diseases: rain splash + warmth
    VECTOR = "vector"  # viruses and insects spread by vectors: warm, not washed out
    MITES = "mites"  # hot and dry
    WATER_STRESS = "water_stress"
    WATERLOGGING = "waterlogging"
    HEAT_STRESS = "heat_stress"
    COLD_STRESS = "cold_stress"
    NOT_WEATHER_DRIVEN = "not_weather_driven"


@dataclass(frozen=True, slots=True)
class Condition:
    archetype: Archetype
    temp_range: tuple[float, float] = (15, 30)


# Keys for rice/tomato/potato match the reference-photo labels, so one key drives both signals.
CONDITIONS: dict[str, Condition] = {
    "blast": Condition(Archetype.HUMID_DISEASE, (20, 30)),
    "brown_spot": Condition(Archetype.HUMID_DISEASE, (20, 32)),
    "bacterial_blight": Condition(Archetype.SPLASH_DISEASE, (25, 35)),
    "tungro": Condition(Archetype.VECTOR, (22, 35)),
    "bacterial_spot": Condition(Archetype.SPLASH_DISEASE, (22, 32)),
    "early_blight": Condition(Archetype.HUMID_DISEASE, (20, 30)),
    "late_blight": Condition(Archetype.HUMID_DISEASE, (10, 25)),
    "leaf_mold": Condition(Archetype.HUMID_DISEASE, (18, 28)),
    "mosaic_virus": Condition(Archetype.VECTOR, (20, 35)),
    "septoria_leaf_spot": Condition(Archetype.HUMID_DISEASE, (15, 27)),
    "spider_mites": Condition(Archetype.MITES, (27, 40)),
    "target_spot": Condition(Archetype.HUMID_DISEASE, (20, 32)),
    "yellow_leaf_curl_virus": Condition(Archetype.VECTOR, (22, 35)),
    "fungal_disease": Condition(Archetype.HUMID_DISEASE, (15, 30)),
    "bacterial_disease": Condition(Archetype.SPLASH_DISEASE, (20, 35)),
    "viral_disease": Condition(Archetype.VECTOR, (20, 35)),
    "insect_pest": Condition(Archetype.VECTOR, (20, 35)),
    "mite_damage": Condition(Archetype.MITES, (27, 40)),
    "water_stress": Condition(Archetype.WATER_STRESS),
    "waterlogging": Condition(Archetype.WATERLOGGING),
    "heat_stress": Condition(Archetype.HEAT_STRESS),
    "cold_stress": Condition(Archetype.COLD_STRESS),
    "nutrient_deficiency": Condition(Archetype.NOT_WEATHER_DRIVEN),
    "chemical_injury": Condition(Archetype.NOT_WEATHER_DRIVEN),
    "other": Condition(Archetype.NOT_WEATHER_DRIVEN),
}
CONDITION_KEYS = tuple(CONDITIONS)

_GENERAL = (
    "fungal_disease",
    "bacterial_disease",
    "viral_disease",
    "insect_pest",
    "mite_damage",
    "water_stress",
    "waterlogging",
    "heat_stress",
    "cold_stress",
    "nutrient_deficiency",
    "chemical_injury",
    "other",
)
_CROP_SPECIFIC: dict[str, tuple[str, ...]] = {
    "rice": ("blast", "brown_spot", "bacterial_blight", "tungro"),
    "tomato": (
        "early_blight",
        "late_blight",
        "bacterial_spot",
        "septoria_leaf_spot",
        "leaf_mold",
        "target_spot",
        "mosaic_virus",
        "yellow_leaf_curl_virus",
        "spider_mites",
    ),
    "potato": ("early_blight", "late_blight"),
}


def condition_keys_for(crop: str | None) -> tuple[str, ...]:
    """Keys the model may use for this crop; specific diseases first, then general groups."""
    if crop is None:
        specific = tuple(dict.fromkeys(k for keys in _CROP_SPECIFIC.values() for k in keys))
        return specific + _GENERAL
    return _CROP_SPECIFIC.get(crop, ()) + _GENERAL


def weather_facts(weather: RecentWeather | None) -> WeatherFacts | None:
    if weather is None or not weather.days:
        return None
    days = weather.days
    mins = [d.temperature_min_c for d in days if d.temperature_min_c is not None]
    maxs = [d.temperature_max_c for d in days if d.temperature_max_c is not None]
    rain = [d.precipitation_mm for d in days if d.precipitation_mm is not None]
    humidity = [
        d.relative_humidity_percent for d in days if d.relative_humidity_percent is not None
    ]
    if not mins or not maxs:
        return None
    means = [
        (d.temperature_min_c + d.temperature_max_c) / 2
        for d in days
        if d.temperature_min_c is not None and d.temperature_max_c is not None
    ]
    facts = WeatherFacts(
        days=len(days),
        start=days[0].date,
        end=days[-1].date,
        temp_min_c=round(min(mins), 1),
        temp_max_c=round(max(maxs), 1),
        temp_mean_c=round(mean(means), 1),
        rain_total_mm=round(sum(rain), 1),
        wet_days=sum(1 for r in rain if r >= WET_DAY_MM),
        humid_days=sum(1 for h in humidity if h >= HUMID_DAY_RH),
        hot_days=sum(1 for t in maxs if t >= HOT_DAY_C),
        cold_nights=sum(1 for t in mins if t <= COLD_NIGHT_C),
        pattern="mild",
    )
    return facts.model_copy(update={"pattern": _pattern(facts)})


def _pattern(f: WeatherFacts) -> str:
    if f.rain_total_mm >= 50 or f.wet_days >= 4:
        return "wet"
    if f.hot_days >= 2 and f.rain_total_mm < 5:
        return "hot_dry"
    if f.cold_nights >= 2:
        return "cold"
    if f.humid_days >= 3 or f.wet_days >= 2:
        return "humid"
    if f.rain_total_mm < 2 and f.humid_days <= 1:
        return "dry"
    return "mild"


def _contribution(signal: EvidenceSignal, points: int, reason: str) -> EvidenceContribution:
    effect = (
        EvidenceEffect.SUPPORTS
        if points > 0
        else EvidenceEffect.WEIGHS_AGAINST
        if points < 0
        else EvidenceEffect.NEUTRAL
    )
    return EvidenceContribution(signal=signal, effect=effect, points=points, reason=reason)


def weather_adjustment(condition_key: str, f: WeatherFacts) -> EvidenceContribution:
    cond = CONDITIONS.get(condition_key, CONDITIONS["other"])
    low, high = cond.temp_range
    in_band = low <= f.temp_mean_c <= high
    band = f"{f.temp_mean_c:g} C average (favoured {low:g}-{high:g} C)"
    moisture = (
        f"humid on {f.humid_days}/{f.days} days, rain on {f.wet_days} ({f.rain_total_mm:g} mm)"
    )
    dry = f.humid_days <= 1 and f.rain_total_mm < 2
    points = 0
    reason = "Recent weather says little about this cause."

    match cond.archetype:
        case Archetype.HUMID_DISEASE:
            moist = f.humid_days >= 3 or f.wet_days >= 2
            very_moist = f.humid_days >= 5 or f.wet_days >= 3
            if moist and in_band:
                points = 10 if very_moist else 6
                reason = f"Moist, mild spell favours it: {moisture}; {band}."
            elif moist:
                points = 2
                reason = f"Moist but outside its usual temperature band: {band}."
            elif dry:
                points = -8
                reason = f"Dry week is unfavourable for it: {moisture}."
        case Archetype.SPLASH_DISEASE:
            splashy = f.wet_days >= 2 or f.rain_total_mm >= 10
            if splashy and in_band:
                points = 10 if f.wet_days >= 3 else 6
                reason = f"Warm rain spreads it by splash: {moisture}; {band}."
            elif splashy:
                points = 2
                reason = f"Rainy but outside its usual temperature band: {band}."
            elif dry:
                points = -8
                reason = f"No rain to spread it: {moisture}."
        case Archetype.VECTOR:
            if in_band and f.rain_total_mm < 30:
                points = 4
                reason = f"Warm weather suits the insects that spread it: {band}."
            elif f.rain_total_mm >= 50:
                points = -3
                reason = f"Heavy rain ({f.rain_total_mm:g} mm) usually knocks back insect vectors."
        case Archetype.MITES:
            if f.temp_mean_c >= low and f.humid_days <= 1 and f.rain_total_mm < 5:
                points = 8
                reason = f"Hot, dry weather favours mites: {band}; {moisture}."
            elif f.humid_days >= 4 or f.rain_total_mm >= 20:
                points = -6
                reason = f"Humid, rainy weather suppresses mites: {moisture}."
        case Archetype.WATER_STRESS:
            if f.rain_total_mm < 5 and (f.hot_days >= 2 or f.temp_max_c >= 32):
                points = 10
                reason = f"Hot and nearly dry: {f.rain_total_mm:g} mm, up to {f.temp_max_c:g} C."
            elif f.rain_total_mm < 5:
                points = 5
                reason = f"Little rain in {f.days} days ({f.rain_total_mm:g} mm)."
            elif f.rain_total_mm >= 25:
                points = -8
                reason = f"{f.rain_total_mm:g} mm of rain makes lack of water less likely."
        case Archetype.WATERLOGGING:
            if f.rain_total_mm >= 50 or f.wet_days >= 4:
                points = 10
                reason = f"Heavy or repeated rain: {f.rain_total_mm:g} mm on {f.wet_days} days."
            elif f.rain_total_mm >= 25:
                points = 4
                reason = f"Substantial rain: {f.rain_total_mm:g} mm."
            elif f.rain_total_mm < 5:
                points = -8
                reason = f"Too little rain to waterlog a field ({f.rain_total_mm:g} mm)."
        case Archetype.HEAT_STRESS:
            if f.hot_days >= 2:
                points = 8
                reason = f"{f.hot_days} days at or above {HOT_DAY_C} C (max {f.temp_max_c:g} C)."
            elif f.temp_max_c < 30:
                points = -6
                reason = f"No hot days: maximum {f.temp_max_c:g} C."
        case Archetype.COLD_STRESS:
            if f.cold_nights >= 1 and f.temp_min_c <= 5:
                points = 8
                reason = f"Cold nights down to {f.temp_min_c:g} C."
            elif f.temp_min_c > 12:
                points = -6
                reason = f"No cold nights: minimum {f.temp_min_c:g} C."
        case Archetype.NOT_WEATHER_DRIVEN:
            pass

    points = max(-WEATHER_MAX_POINTS, min(WEATHER_MAX_POINTS, points))
    return _contribution(EvidenceSignal.WEATHER, points, reason)


_FIELD_WIDE = {
    Archetype.WATER_STRESS,
    Archetype.WATERLOGGING,
    Archetype.HEAT_STRESS,
    Archetype.COLD_STRESS,
}


def satellite_adjustment(
    condition_key: str, sat: SatelliteAnalysis, facts: WeatherFacts | None
) -> EvidenceContribution:
    """Bounded points from the field's greenness trend; call only for interpretable analyses."""
    cond = CONDITIONS.get(condition_key, CONDITIONS["other"])
    declining = sat.trend == VegetationTrend.DECLINING
    improving = sat.trend == VegetationTrend.IMPROVING
    drying = sat.ndmi_trend == VegetationTrend.DECLINING
    dry_weather = facts is not None and facts.rain_total_mm < 5
    wet_weather = facts is not None and (facts.rain_total_mm >= 25 or facts.wet_days >= 3)
    change = f"greenness {sat.ndvi_change:+.2f}" if sat.ndvi_change is not None else "greenness"
    points = 0
    reason = "Field greenness says little about this cause."

    match cond.archetype:
        case Archetype.WATER_STRESS:
            if declining and (drying or dry_weather):
                points = 6
                reason = f"Field is losing greenness and drying ({change})."
            elif improving:
                points = -4
                reason = f"Field is getting greener ({change}); a water shortage is less likely."
            elif not declining:
                points = -2
                reason = "Field greenness is steady; no field-wide water stress seen."
        case Archetype.WATERLOGGING:
            if declining and wet_weather:
                points = 4
                reason = f"Field lost greenness after heavy rain ({change})."
            elif improving:
                points = -3
                reason = f"Field is getting greener ({change})."
        case Archetype.HEAT_STRESS | Archetype.COLD_STRESS:
            if declining:
                points = 3
                reason = f"Field-wide loss of greenness fits a weather shock ({change})."
            elif improving:
                points = -3
                reason = f"Field is getting greener ({change})."
        case Archetype.NOT_WEATHER_DRIVEN:
            if condition_key == "nutrient_deficiency" and declining and not dry_weather:
                points = 3
                reason = f"Greenness is falling without a dry spell to explain it ({change})."
        case _:
            if declining and not dry_weather:
                points = 4
                reason = f"Greenness falling field-wide without drought ({change}): spreading?"
            elif declining:
                reason = f"Greenness is falling, but dry weather could explain it ({change})."
            else:
                trend = "getting greener" if improving else "steady"
                reason = f"Field is {trend}; consistent with a problem on some plants only."

    points = max(-SATELLITE_MAX_POINTS, min(SATELLITE_MAX_POINTS, points))
    return _contribution(EvidenceSignal.SATELLITE, points, reason)


def weather_score(points: int) -> int:
    """Map weather points to the legacy 0-100 scale (50 = neutral)."""
    return round(50 + 50 * points / WEATHER_MAX_POINTS)


def satellite_score(points: int) -> int:
    return round(50 + 50 * points / SATELLITE_MAX_POINTS)
