"""
Conversion Model: ΔE = C² * Δm + λ * Input - γ * E + noise
Implements energy dynamics from identity mass changes and input/dissipation.
"""

from __future__ import annotations

from typing import Optional, Tuple
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


class ConversionModel:
    """
    Compute energy changes from conversion law.
    
    Formula: E_{t+1} = E_t + λ*D*T - γ*E_t + C²*(m_{t+1} - m_t) + ε_E
    
    Where:
        C² = conversion coefficient (default 2.0)
        λ = input scale (default 0.5)
        γ = dissipation rate (default 0.3)
        ε_E = noise (Gaussian, σ=0.2)
    """
    
    def __init__(self, C2: float = 2.0, lam: float = 0.5, gamma: float = 0.3, 
                 sigma_E: float = 0.2):
        """
        Initialize conversion model.
        
        Args:
            C2: Conversion coefficient (C squared)
            lam: Input scale parameter
            gamma: Dissipation rate
            sigma_E: Noise standard deviation
        """
        self.C2 = C2
        self.lam = lam
        self.gamma = gamma
        self.sigma_E = sigma_E
    
    def compute_input(self, D: int, T: float) -> float:
        """
        Compute input energy from dose and arousal.
        
        Args:
            D: Dose
            T: Arousal
        
        Returns:
            Input energy term
        """
        return self.lam * D * T
    
    def compute_dissipation(self, E: float) -> float:
        """
        Compute dissipation energy loss.
        
        Args:
            E: Current energy
        
        Returns:
            Energy loss from dissipation
        """
        return self.gamma * E
    
    def compute_delta_E(self, E: float, D: int, T: float, delta_m: float,
                       noise: bool = False, rng: Optional[np.random.Generator] = None) -> float:
        """
        Compute energy change for one timestep.
        
        Args:
            E: Current energy
            D: Dose
            T: Arousal
            delta_m: Change in identity mass
            noise: Whether to add stochastic noise
            rng: Random number generator (used if noise=True)
        
        Returns:
            Change in energy (ΔE)
        """
        input_term = self.compute_input(D, T)
        dissipation = self.compute_dissipation(E)
        conversion = self.C2 * delta_m
        
        delta_E = input_term - dissipation + conversion
        
        if noise and rng is not None:
            delta_E += rng.normal(0, self.sigma_E)
        
        return delta_E
    
    def update_state(self, state: EmotionalState, delta_m: float, 
                    noise: bool = False, rng: Optional[np.random.Generator] = None) -> Tuple[EmotionalState, dict]:
        """
        Update state energy given mass change.
        
        Args:
            state: Current emotional state
            delta_m: Change in identity mass
            noise: Whether to include stochastic noise
            rng: Random number generator
        
        Returns:
            (updated_state, diagnostics)
        """
        delta_E = self.compute_delta_E(state.E, state.D, state.T, delta_m, noise, rng)
        E_new = max(0.0, state.E + delta_E)
        m_new = max(0.1, state.m + delta_m)
        
        state.E = E_new
        state.m = m_new
        state._recompute_derived()
        
        diagnostics = {
            'delta_E': delta_E,
            'input': self.compute_input(state.D, state.T),
            'dissipation': self.compute_dissipation(state.E),
            'conversion': self.C2 * delta_m,
            'E_new': E_new,
            'm_new': m_new,
            'alpha_new': state.alpha
        }
        
        return state, diagnostics
    
    def to_dict(self):
        """Serialize model parameters."""
        return {
            'C2': self.C2,
            'lam': self.lam,
            'gamma': self.gamma,
            'sigma_E': self.sigma_E
        }
    
    @classmethod
    def from_dict(cls, data):
        """Deserialize model from parameters."""
        return cls(
            C2=data.get('C2', 2.0),
            lam=data.get('lam', 0.5),
            gamma=data.get('gamma', 0.3),
            sigma_E=data.get('sigma_E', 0.2)
        )
