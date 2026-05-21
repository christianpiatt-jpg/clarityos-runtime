from .mapping import pressure_to_somatic

class SomaticRegister:
    def __init__(self, stress_score: float, stress_band: str):
        self.stress_score = stress_score
        self.stress_band = stress_band

    @classmethod
    def from_pressure(cls, pressure_score: float):
        m = pressure_to_somatic(pressure_score)
        return cls(m["stress_score"], m["stress_band"])
