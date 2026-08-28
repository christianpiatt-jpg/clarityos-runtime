"""
Relational Model: P_perc = r * P
Implements relational filtering of objective pressure into perceived pressure.
"""

from __future__ import annotations

from typing import Tuple, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - annotation only, never imported at runtime
    import numpy as np

# ★ numpy is a TYPE ANNOTATION ONLY here: `Optional[np.random.Generator]` on
# the noise path, which is guarded by `noise=False, rng=None` defaults and is
# never entered unless a caller passes a Generator in. The TYPE_CHECKING guard
# keeps the annotation honest for mypy while ensuring the runtime NEVER
# imports numpy -- ClarityOS_Code does not ship it, and does not need to.
# `from __future__ import annotations` makes the annotations lazy strings so
# they resolve without the module present.
from .state import EmotionalState


class RelationalModel:
    """
    Compute perceived pressure from objective pressure and relational registration.
    
    Formula: P_perc = r * P + ε_P
    
    Where:
        P = objective pressure
        r = relational registration (how much pressure agent internalizes)
        ε_P = noise (Gaussian, σ=0.1)
    
    Interpretation:
        r < 1.0: agent buffers/deflects pressure (resilient)
        r = 1.0: agent internalizes pressure linearly (neutral)
        r > 1.0: agent amplifies pressure (sensitive)
    """
    
    def __init__(self, sigma_P: float = 0.1):
        """
        Initialize relational model.
        
        Args:
            sigma_P: Noise standard deviation for perceived pressure
        """
        self.sigma_P = sigma_P
    
    def compute_perceived_pressure(self, P: float, r: float, 
                                   noise: bool = False, 
                                   rng: Optional[np.random.Generator] = None) -> float:
        """
        Compute perceived pressure with relational filtering.
        
        Args:
            P: Objective pressure
            r: Relational registration (typically 0.6-1.4)
            noise: Whether to add stochastic noise
            rng: Random number generator
        
        Returns:
            Perceived pressure (can be negative due to noise)
        """
        P_perc = r * P
        
        if noise and rng is not None:
            P_perc += rng.normal(0, self.sigma_P)
        
        return P_perc
    
    def relational_resilience(self, r: float) -> float:
        """
        Compute resilience score from relational registration.
        
        resilience = 1 / r  (lower r = higher resilience)
        
        Args:
            r: Relational registration
        
        Returns:
            Resilience score (1.0 is neutral)
        """
        if r <= 0:
            return float('inf')
        return 1.0 / r
    
    def relational_sensitivity(self, r: float) -> float:
        """
        Compute sensitivity score from relational registration.
        
        sensitivity = r  (higher r = higher sensitivity)
        
        Args:
            r: Relational registration
        
        Returns:
            Sensitivity score (1.0 is neutral)
        """
        return max(0.0, r)
    
    def update_state(self, state: EmotionalState) -> Tuple[EmotionalState, dict]:
        """
        Update state with relational filtering.
        
        Args:
            state: Current emotional state (must have P set)
        
        Returns:
            (updated_state, diagnostics)
        """
        if not hasattr(state, 'P'):
            return state, {'error': 'State missing P value'}
        
        P_perc = self.compute_perceived_pressure(state.P, state.r, noise=False)
        state.P_perc = P_perc
        
        diagnostics = {
            'P': state.P,
            'r': state.r,
            'P_perc': P_perc,
            'resilience': self.relational_resilience(state.r),
            'sensitivity': self.relational_sensitivity(state.r),
            'pressure_amplification': P_perc / state.P if state.P > 0 else 0.0
        }
        
        return state, diagnostics
    
    def estimate_relational_registration(self, P_perc: float, P: float) -> float:
        """
        Estimate r from observed perceived and objective pressure.
        
        r = P_perc / P (with protection against division by zero)
        
        Args:
            P_perc: Observed perceived pressure
            P: Observed objective pressure
        
        Returns:
            Estimated r value
        """
        if P <= 0:
            return 1.0
        
        r = P_perc / P
        return max(0.1, r)  # clamp to reasonable range
    
    def to_dict(self):
        """Serialize model parameters."""
        return {'sigma_P': self.sigma_P}
    
    @classmethod
    def from_dict(cls, data):
        """Deserialize model from parameters."""
        return cls(sigma_P=data.get('sigma_P', 0.1))
