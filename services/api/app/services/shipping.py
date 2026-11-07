"""Simulated shipping estimates. All values are DEMO numbers, never real carrier quotes."""

SIMULATED_RATES = {"same_city": 10_000, "same_province": 20_000, "other": 35_000}


def estimate(from_city: str, from_province: str, to_city: str, to_province: str) -> int:
    if from_city.strip().lower() == to_city.strip().lower():
        return SIMULATED_RATES["same_city"]
    if from_province.strip().lower() == to_province.strip().lower():
        return SIMULATED_RATES["same_province"]
    return SIMULATED_RATES["other"]
