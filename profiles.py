"""Explicit, fixed firmware presets; no arbitrary SMM commands or PWM."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    description: str
    thermal: str | None = None
    level: int | None = None


PROFILES = {
    p.id: p for p in (
        Profile("auto", "AUTO", "Let the BIOS manage fan speed."),
        Profile("balanced", "Balanced", "Everyday performance and automatic cooling.", "balanced"),
        Profile("cool", "Cool", "Dell's cooler-surface thermal policy.", "cool"),
        Profile("quiet", "Quiet", "Dell's quieter thermal policy.", "quiet"),
        Profile("ultra", "Ultra Performance", "Full Dell performance with automatic fan control.", "performance"),
        Profile("low", "Manual Low", "Both fans at nominal 2,400 RPM, with a timer.", level=1),
        Profile("high", "Manual High", "Both fans at nominal 4,000 RPM, with a timer.", level=2),
    )
}


def resolve_profile(profile_id: str, seconds: int) -> Profile:
    if profile_id not in PROFILES:
        raise ValueError("Unknown profile")
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 3600:
        raise ValueError("Manual duration must be 1..3600 seconds")
    return PROFILES[profile_id]


def verify_temperatures(status: dict):
    values = status.get("temperatures_c", [])
    if len(values) != 2 or any(not isinstance(t, (int, float)) or not 1 <= t < 90 for t in values):
        raise RuntimeError("Firmware temperature is missing or at least 90 C. Returning AUTO.")
