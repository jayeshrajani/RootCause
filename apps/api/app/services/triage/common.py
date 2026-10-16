"""Evidence and provenance shared by every triage engine."""

from app.models.report import FarmerReport
from app.schemas.satellite import SatelliteAnalysis, SatelliteLimitation, SatelliteStatus
from app.schemas.triage import (
    DataSource,
    DataSourceStatus,
    Evidence,
    EvidenceAvailability,
    SourceKind,
    SymptomDuration,
)

DURATION_LABELS: dict[SymptomDuration, str] = {
    SymptomDuration.LESS_THAN_3_DAYS: "less than 3 days",
    SymptomDuration.THREE_TO_7_DAYS: "3 to 7 days",
    SymptomDuration.ONE_TO_2_WEEKS: "1 to 2 weeks",
    SymptomDuration.MORE_THAN_2_WEEKS: "more than 2 weeks",
    SymptomDuration.NOT_SURE: "not sure",
}


def crop_name(report: FarmerReport) -> str | None:
    return report.crop.value.replace("_", " ") if report.crop else None


def duration_label(report: FarmerReport) -> str:
    return DURATION_LABELS[report.symptom_duration] if report.symptom_duration else "not given"


def approximate_location(report: FarmerReport) -> str | None:
    if report.latitude is None or report.longitude is None:
        return None
    latitude_direction = "N" if report.latitude >= 0 else "S"
    longitude_direction = "E" if report.longitude >= 0 else "W"
    return (
        f"{abs(report.latitude):.2f}° {latitude_direction}, "
        f"{abs(report.longitude):.2f}° {longitude_direction}"
    )


def recent_weather_summary(report: FarmerReport) -> str | None:
    if report.weather is None or not report.weather.days:
        return None
    days = report.weather.days
    temperatures_min = [day.temperature_min_c for day in days if day.temperature_min_c is not None]
    temperatures_max = [day.temperature_max_c for day in days if day.temperature_max_c is not None]
    rain_values = [day.precipitation_mm for day in days if day.precipitation_mm is not None]
    humidity_values = [
        day.relative_humidity_percent for day in days if day.relative_humidity_percent is not None
    ]
    language = report.response_language.value
    labels = {
        "en": (
            "Previous",
            "completed days",
            "temperature",
            "rain",
            "mean humidity",
            "Open-Meteo regional estimates, not field measurements.",
        ),
        "hi": (
            "पिछले",
            "पूरे दिन",
            "तापमान",
            "बारिश",
            "औसत नमी",
            "Open-Meteo के क्षेत्रीय अनुमान, खेत पर माप नहीं।",
        ),
        "pa": (
            "ਪਿਛਲੇ",
            "ਪੂਰੇ ਦਿਨ",
            "ਤਾਪਮਾਨ",
            "ਮੀਂਹ",
            "ਔਸਤ ਨਮੀ",
            "Open-Meteo ਦੇ ਖੇਤਰੀ ਅੰਦਾਜ਼ੇ, ਖੇਤ ਦੀ ਮਾਪ ਨਹੀਂ।",
        ),
        "es": (
            "Últimos",
            "días completos",
            "temperatura",
            "lluvia",
            "humedad media",
            "Estimaciones regionales de Open-Meteo, no mediciones del campo.",
        ),
        "fr": (
            "Sur les",
            "derniers jours complets",
            "température",
            "pluie",
            "humidité moyenne",
            "Estimations régionales Open-Meteo, pas des mesures du champ.",
        ),
    }
    previous, completed, temperature_label, rain_label, humidity_label, caveat = labels.get(
        language, labels["en"]
    )
    details = []
    if temperatures_min and temperatures_max:
        temperature_range = f"{min(temperatures_min):.1f}–{max(temperatures_max):.1f}°C"
        details.append(f"{temperature_label} {temperature_range}")
    if rain_values:
        details.append(f"{rain_label} {sum(rain_values):.1f} mm")
    if humidity_values:
        details.append(f"{humidity_label} {sum(humidity_values) / len(humidity_values):.0f}%")
    if not details:
        return None
    return (
        f"{previous} {len(days)} {completed} ({days[0].date} – {days[-1].date}): "
        f"{'; '.join(details)}. {caveat}"
    )


def farmer_report_evidence(report: FarmerReport) -> Evidence:
    parts = [f"Crop: {crop_name(report) or 'not specified'}", f"duration: {duration_label(report)}"]
    if report.description:
        observation = (
            f"Farmer's description: \u201c{report.description}\u201d ({', '.join(parts)})."
        )
    else:
        observation = f"No written description was given ({', '.join(parts)})."
    return Evidence(
        id="ev_farmer_report",
        source=SourceKind.FARMER_REPORT,
        availability=EvidenceAvailability.AVAILABLE,
        observation=observation,
        observed_at=report.received_at,
    )


def not_integrated_evidence(
    *, include_weather: bool = True, include_references: bool = True, include_satellite: bool = True
) -> list[Evidence]:
    evidence = [
        Evidence(
            id="ev_knowledge",
            source=SourceKind.KNOWLEDGE_BASE,
            availability=EvidenceAvailability.NOT_INTEGRATED,
            observation="No agricultural guidance was retrieved; no sources are cited.",
        ),
    ]
    if include_satellite:
        evidence.insert(
            0,
            Evidence(
                id="ev_satellite",
                source=SourceKind.SATELLITE,
                availability=EvidenceAvailability.NOT_INTEGRATED,
                observation="No satellite vegetation data was retrieved.",
            ),
        )
    if include_references:
        evidence.append(
            Evidence(
                id="ev_references",
                source=SourceKind.REFERENCE_PHOTOS,
                availability=EvidenceAvailability.NOT_INTEGRATED,
                observation="No labelled reference photos were compared.",
            )
        )
    if include_weather:
        evidence.insert(
            0,
            Evidence(
                id="ev_weather",
                source=SourceKind.WEATHER,
                availability=EvidenceAvailability.NOT_INTEGRATED,
                observation="No weather data was retrieved. Do not assume conditions were normal.",
            ),
        )
    return evidence


def weather_evidence(report: FarmerReport) -> Evidence:
    if report.weather is None:
        return Evidence(
            id="ev_weather",
            source=SourceKind.WEATHER,
            availability=EvidenceAvailability.UNAVAILABLE,
            observation=report.weather_unavailable_reason or "No weather data was retrieved.",
        )
    daily_summary = "; ".join(
        f"{day.date}: min {day.temperature_min_c if day.temperature_min_c is not None else 'n/a'}"
        f" C, max {day.temperature_max_c if day.temperature_max_c is not None else 'n/a'} C, "
        f"rain {day.precipitation_mm if day.precipitation_mm is not None else 'n/a'} mm, "
        f"mean relative humidity "
        f"{day.relative_humidity_percent if day.relative_humidity_percent is not None else 'n/a'}%"
        for day in report.weather.days
    )
    return Evidence(
        id="ev_weather",
        source=SourceKind.WEATHER,
        availability=EvidenceAvailability.AVAILABLE,
        observation=(
            "Open-Meteo model-based estimates for the previous completed local days "
            f"(not measurements from the field): {daily_summary}."
        ),
    )


def weather_source(report: FarmerReport) -> DataSource:
    used = report.weather is not None
    return DataSource(
        id="src_weather",
        name="Open-Meteo recent weather",
        kind=SourceKind.WEATHER,
        status=DataSourceStatus.USED if used else DataSourceStatus.UNAVAILABLE,
        description=(
            "Recent model-based daily temperature, precipitation and humidity estimates."
            if used
            else report.weather_unavailable_reason or "No weather data was retrieved."
        ),
        retrieved_at=report.weather.retrieved_at if report.weather else None,
    )


def farmer_report_source() -> DataSource:
    return DataSource(
        id="src_farmer_report",
        name="Farmer report",
        kind=SourceKind.FARMER_REPORT,
        status=DataSourceStatus.USED,
        description="Description and any optional details the farmer added.",
    )


def reference_evidence(report: FarmerReport) -> Evidence:
    votes = report.references
    if votes is None:
        return Evidence(
            id="ev_references",
            source=SourceKind.REFERENCE_PHOTOS,
            availability=EvidenceAvailability.UNAVAILABLE,
            observation=report.references_unavailable_reason
            or "No labelled reference photos were compared.",
        )
    shares = ", ".join(f"{label.replace('_', ' ')} {count}" for label, count in votes.counts)
    return Evidence(
        id="ev_references",
        source=SourceKind.REFERENCE_PHOTOS,
        availability=EvidenceAvailability.AVAILABLE,
        observation=(
            f"Labels of the {votes.total} public-dataset {votes.crop} photos that look most "
            f"like these photos: {shares}. Visual similarity only, not a diagnosis."
        ),
    )


def reference_source(report: FarmerReport) -> DataSource:
    votes = report.references
    return DataSource(
        id="src_references",
        name="Reference photo library",
        kind=SourceKind.REFERENCE_PHOTOS,
        status=DataSourceStatus.USED if votes else DataSourceStatus.UNAVAILABLE,
        description=(
            "DINOv2 visual similarity to labelled public photos (PlantDoc, PlantVillage, "
            f"Mendeley rice), index {votes.index_version}. Rice, tomato and potato only."
            if votes
            else report.references_unavailable_reason
            or "No labelled reference photos were compared."
        ),
    )


def not_integrated_sources(
    *, include_weather: bool = True, include_references: bool = True, include_satellite: bool = True
) -> list[DataSource]:
    sources = [
        DataSource(
            id="src_knowledge",
            name="Agricultural knowledge base",
            kind=SourceKind.KNOWLEDGE_BASE,
            status=DataSourceStatus.NOT_INTEGRATED,
            description="Planned for Milestone 4.",
        ),
    ]
    if include_satellite:
        sources.insert(
            0,
            DataSource(
                id="src_satellite",
                name="Satellite vegetation indices",
                kind=SourceKind.SATELLITE,
                status=DataSourceStatus.NOT_INTEGRATED,
                description="Satellite vegetation evidence is not enabled for this mode.",
            ),
        )
    if include_references:
        sources.append(
            DataSource(
                id="src_references",
                name="Reference photo library",
                kind=SourceKind.REFERENCE_PHOTOS,
                status=DataSourceStatus.NOT_INTEGRATED,
                description="Comparison with labelled public crop photos is not enabled.",
            )
        )
    if include_weather:
        sources.insert(
            0,
            DataSource(
                id="src_weather",
                name="Weather (Open-Meteo)",
                kind=SourceKind.WEATHER,
                status=DataSourceStatus.NOT_INTEGRATED,
                description="Weather lookup is not enabled for this analysis mode.",
            ),
        )
    return sources


_SATELLITE_LIMITATION_TEXT: dict[SatelliteLimitation, str] = {
    SatelliteLimitation.APPROXIMATE_AREA: (
        "sampled from a circle around the given point, not an exact field boundary"
    ),
    SatelliteLimitation.APPROXIMATE_LOCATION: (
        "the location was only approximate (~1 km), so this describes the surrounding area, "
        "not necessarily this field"
    ),
    SatelliteLimitation.NO_BASELINE: "no clear earlier scene to compare against",
    SatelliteLimitation.SINGLE_OBSERVATION: "only one clear recent scene",
    SatelliteLimitation.PARTIAL_COVERAGE: "part of the area was hidden by cloud or shadow",
    SatelliteLimitation.STALE_OBSERVATION: "the latest clear scene is several weeks old",
    SatelliteLimitation.LOW_VEGETATION: (
        "low green cover, which can be bare soil, a harvested field or a young crop rather "
        "than stress"
    ),
}


def satellite_summary(satellite: SatelliteAnalysis) -> str | None:
    """Plain-English summary of measured values for the model prompt and evidence list."""
    if satellite.status != SatelliteStatus.AVAILABLE or satellite.ndvi is None:
        return None
    area = (
        f"{satellite.buffer_m} m circle around the point"
        if satellite.buffer_m
        else "the supplied field boundary"
    )
    parts = [
        f"Latest clear Sentinel-2 scene {satellite.observation_date} "
        f"({satellite.observation_age_days} days before analysis), {area}: "
        f"NDVI {satellite.ndvi:.2f}"
        + (f", NDMI {satellite.ndmi:.2f}" if satellite.ndmi is not None else "")
        + (
            f", {satellite.valid_pixel_coverage:.0%} of the area cloud-free"
            if satellite.valid_pixel_coverage is not None
            else ""
        )
        + "."
    ]
    recent, baseline = satellite.recent_window, satellite.baseline_window
    if recent and baseline and satellite.ndvi_change is not None:
        parts.append(
            f"Median NDVI {recent.ndvi_median} over {recent.start}–{recent.end} "
            f"({recent.clear_observations} clear scenes) vs {baseline.ndvi_median} over "
            f"{baseline.start}–{baseline.end} ({baseline.clear_observations} clear scenes): "
            f"change {satellite.ndvi_change:+.2f} ({satellite.trend.value})."
        )
        if satellite.ndmi_change is not None:
            parts.append(
                f"NDMI change {satellite.ndmi_change:+.2f} ({satellite.ndmi_trend.value})."
            )
    if satellite.limitations:
        notes = "; ".join(_SATELLITE_LIMITATION_TEXT[item] for item in satellite.limitations)
        parts.append(f"Limitations: {notes}.")
    return " ".join(parts)


def satellite_evidence(report: FarmerReport) -> Evidence:
    satellite = report.satellite
    summary = satellite_summary(satellite) if satellite else None
    if satellite is None or summary is None:
        return Evidence(
            id="ev_satellite",
            source=SourceKind.SATELLITE,
            availability=EvidenceAvailability.UNAVAILABLE,
            observation=(satellite.message if satellite and satellite.message else None)
            or "No satellite vegetation data was retrieved. Do not assume the crop canopy "
            "is normal.",
        )
    return Evidence(
        id="ev_satellite",
        source=SourceKind.SATELLITE,
        availability=EvidenceAvailability.AVAILABLE,
        observation=f"Satellite measurements (vegetation indices, not a diagnosis): {summary}",
    )


def satellite_source(report: FarmerReport) -> DataSource:
    satellite = report.satellite
    used = satellite is not None and satellite.status == SatelliteStatus.AVAILABLE
    return DataSource(
        id="src_satellite",
        name="Google Earth Engine / Sentinel-2",
        kind=SourceKind.SATELLITE,
        status=DataSourceStatus.USED if used else DataSourceStatus.UNAVAILABLE,
        description=(
            "Cloud-masked Sentinel-2 NDVI (greenness) and NDMI (moisture) with a trend "
            "versus the previous window."
            if used
            else (satellite.message if satellite and satellite.message else None)
            or "No satellite vegetation data was retrieved."
        ),
        retrieved_at=satellite.retrieved_at if satellite and used else None,
    )
