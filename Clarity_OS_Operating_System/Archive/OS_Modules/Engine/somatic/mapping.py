def pressure_to_somatic(pressure_score: float) -> dict:
    # clamp to [0.0, 1.0]
    p = max(0.0, min(1.0, pressure_score))

    if p <= 0.30:
        band = "low"
    elif p < 0.75:
        band = "medium"
    else:
        band = "high"

    return {
        "stress_score": p,
        "stress_band": band,
    }
