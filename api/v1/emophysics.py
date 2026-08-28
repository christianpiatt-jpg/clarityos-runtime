"""
Emotional Physics API v1
FastAPI endpoints for pressure, conversion, threshold, and relational models.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - see the note below
    import numpy as np

# ★ VENDORED 2026-08-28. numpy is imported LAZILY, inside the one endpoint
# that can use it (/simulate with include_noise=true), because ClarityOS_Code
# does not ship numpy and the other six endpoints do not need it. An
# unconditional top-level import would make the whole router unimportable.

from engine.emophysics import (
    EmotionalState, PressureModel, ConversionModel,
    ThresholdModel, RelationalModel
)

router = APIRouter(prefix="/api/v1/emophysics", tags=["emophysics"])

# Initialize models with validated parameters
pressure_model = PressureModel(B=1.2)
conversion_model = ConversionModel(C2=2.0, lam=0.5, gamma=0.3, sigma_E=0.2)
threshold_model = ThresholdModel(alpha_c=1.5, beta_0=-5.48, beta_1=3.20)
relational_model = RelationalModel(sigma_P=0.1)


# Request/Response Models
class PressureRequest(BaseModel):
    D: int
    T: float
    N: float
    
    class Config:
        schema_extra = {
            "example": {
                "D": 5,
                "T": 2.5,
                "N": 5.0
            }
        }


class PressureResponse(BaseModel):
    P: float
    elastic_D: float
    elastic_T: float
    elastic_N: float
    metadata: Dict[str, Any] = {}


class ConversionRequest(BaseModel):
    E: float
    D: int
    T: float
    delta_m: float
    include_noise: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "E": 1.0,
                "D": 5,
                "T": 2.0,
                "delta_m": 0.1
            }
        }


class ConversionResponse(BaseModel):
    delta_E: float
    input_term: float
    dissipation: float
    conversion_term: float
    E_new: float
    metadata: Dict[str, Any] = {}


class ThresholdRequest(BaseModel):
    E: float
    m: float
    use_hard_threshold: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "E": 1.5,
                "m": 1.0
            }
        }


class ThresholdResponse(BaseModel):
    alpha: float
    is_collapse: bool
    collapse_probability: float
    stability_margin: float
    time_to_collapse: Optional[float] = None
    metadata: Dict[str, Any] = {}


class StateRequest(BaseModel):
    E: float = 0.5
    m: float = 3.0
    r: float = 1.0
    N: float = 5.0
    D: int = 0
    T: float = 0.5


class FullStateResponse(BaseModel):
    state: Dict[str, Any]
    pressure: Dict[str, Any]
    conversion: Dict[str, Any]
    threshold: Dict[str, Any]
    relational: Dict[str, Any]


# Endpoints

@router.post("/pressure", response_model=PressureResponse)
def compute_pressure(req: PressureRequest) -> PressureResponse:
    """
    Compute system pressure from dose, arousal, and narrative compression.
    
    P = B * (D * T) / N
    """
    try:
        P = pressure_model.compute(req.D, req.T, req.N)
        e_D, e_T, e_N = pressure_model.compute_elasticity(req.D, req.T, req.N)
        
        return PressureResponse(
            P=P,
            elastic_D=e_D,
            elastic_T=e_T,
            elastic_N=e_N,
            metadata={"B": pressure_model.B}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/convert", response_model=ConversionResponse)
def compute_conversion(req: ConversionRequest) -> ConversionResponse:
    """
    Compute energy change from conversion law.
    
    ΔE = C² * Δm + λ * (D*T) - γ * E + noise
    """
    try:
        # Lazy: only the noise path needs numpy. Without it, include_noise
        # is refused explicitly rather than silently producing a noiseless
        # result that looks like a noisy one.
        rng = None
        if req.include_noise:
            try:
                import numpy as np  # noqa: F811 - runtime-optional
            except ImportError:
                raise HTTPException(
                    status_code=501,
                    detail="include_noise requires numpy, which is not installed",
                )
            rng = np.random.default_rng()
        delta_E = conversion_model.compute_delta_E(
            req.E, req.D, req.T, req.delta_m,
            noise=req.include_noise, rng=rng
        )
        E_new = max(0.0, req.E + delta_E)
        
        return ConversionResponse(
            delta_E=delta_E,
            input_term=conversion_model.compute_input(req.D, req.T),
            dissipation=conversion_model.compute_dissipation(req.E),
            conversion_term=conversion_model.C2 * req.delta_m,
            E_new=E_new,
            metadata={"C2": conversion_model.C2, "lambda": conversion_model.lam}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/threshold", response_model=ThresholdResponse)
def detect_collapse(req: ThresholdRequest) -> ThresholdResponse:
    """
    Detect collapse using collapse ratio α = E/m.
    
    Returns alpha, collapse flag, and probability.
    """
    try:
        alpha = threshold_model.compute_alpha(req.E, req.m)
        is_collapse = threshold_model.is_collapse(alpha, hard_threshold=req.use_hard_threshold)
        prob = threshold_model.collapse_probability(alpha)
        margin = threshold_model.compute_stability_margin(req.E, req.m)
        
        return ThresholdResponse(
            alpha=alpha,
            is_collapse=is_collapse,
            collapse_probability=prob,
            stability_margin=margin,
            metadata={"alpha_c": threshold_model.alpha_c}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/relational", response_model=Dict[str, Any])
def compute_relational(P: float, r: float) -> Dict[str, Any]:
    """
    Compute perceived pressure with relational filtering.
    
    P_perc = r * P
    """
    try:
        P_perc = relational_model.compute_perceived_pressure(P, r, noise=False)
        resilience = relational_model.relational_resilience(r)
        sensitivity = relational_model.relational_sensitivity(r)
        
        return {
            "P": P,
            "r": r,
            "P_perc": P_perc,
            "resilience": resilience,
            "sensitivity": sensitivity
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulate", response_model=FullStateResponse)
def simulate_full_state(req: StateRequest) -> FullStateResponse:
    """
    Full emotional physics simulation for a single state.
    
    Computes pressure, energy dynamics, collapse detection, and relational filtering.
    """
    try:
        # Create state
        state = EmotionalState(E=req.E, m=req.m, r=req.r, N=req.N, D=req.D, T=req.T)
        
        # Compute pressure
        state = pressure_model.update_state(state)
        pressure_diag = {
            "P": state.P,
            "P_perc": state.P_perc,
            "elasticity": pressure_model.compute_elasticity(req.D, req.T, req.N)
        }
        
        # Compute threshold
        _, threshold_diag = threshold_model.update_state(state)
        
        # Compute relational
        _, relational_diag = relational_model.update_state(state)
        
        # Conversion (hypothetical delta_m = 0.1)
        state_converted, conversion_diag = conversion_model.update_state(state, delta_m=0.0)
        
        return FullStateResponse(
            state=state.to_dict(),
            pressure=pressure_diag,
            conversion=conversion_diag,
            threshold=threshold_diag,
            relational=relational_diag
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models/config")
def get_model_config() -> Dict[str, Any]:
    """Return current model parameters."""
    return {
        "pressure": pressure_model.to_dict(),
        "conversion": conversion_model.to_dict(),
        "threshold": threshold_model.to_dict(),
        "relational": relational_model.to_dict()
    }


@router.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
