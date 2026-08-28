"""
Threshold Model: Collapse detection using α = E/m
Implements logistic collapse prediction based on collapse ratio.
"""

import math
from typing import Tuple
from .state import EmotionalState


def expit(x: float) -> float:
    """Logistic function, 1/(1+e^-x). Inlined at vendoring.

    ★ scipy was this engine's ONLY real third-party dependency and it was
    used for exactly one call. The branch is the standard overflow-safe
    formulation: exp(-x) overflows for large negative x, exp(x) for large
    positive, so each side uses the form that cannot.

    Verified against the upstream engine's own suite: 15/15 with this
    substituted for scipy.special.expit.
    """
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class ThresholdModel:
    """
    Detect and predict collapse events using α = E/m threshold.
    
    Collapse occurs when emotional energy exceeds identity mass capacity.
    Uses logistic regression for probability estimation.
    
    Formula: P(collapse) = 1 / (1 + exp(-β₀ - β₁*α))
    """
    
    def __init__(self, alpha_c: float = 1.5, beta_0: float = -5.48, beta_1: float = 3.20):
        """
        Initialize threshold model.
        
        Args:
            alpha_c: Hard threshold for collapse (α > α_c triggers collapse)
            beta_0: Logistic intercept
            beta_1: Logistic coefficient on α
        """
        self.alpha_c = alpha_c
        self.beta_0 = beta_0
        self.beta_1 = beta_1
    
    def compute_alpha(self, E: float, m: float) -> float:
        """
        Compute collapse ratio α = E/m.
        
        Args:
            E: Emotional energy
            m: Identity mass
        
        Returns:
            Collapse ratio (can be arbitrarily large)
        """
        if m <= 0:
            return float('inf')
        return E / m
    
    def is_collapse(self, alpha: float, hard_threshold: bool = True) -> bool:
        """
        Determine if collapse occurs (hard threshold).
        
        Args:
            alpha: Collapse ratio E/m
            hard_threshold: If True, use α_c; if False, use logistic
        
        Returns:
            Boolean indicating collapse
        """
        if hard_threshold:
            return alpha > self.alpha_c
        else:
            prob = self.collapse_probability(alpha)
            return prob > 0.5
    
    def collapse_probability(self, alpha: float) -> float:
        """
        Compute collapse probability from α using logistic model.
        
        P(collapse | α) = 1 / (1 + exp(-β₀ - β₁*α))
        
        Args:
            alpha: Collapse ratio
        
        Returns:
            Probability in [0, 1]
        """
        logit = self.beta_0 + self.beta_1 * alpha
        prob = expit(logit)
        return prob
    
    def update_state(self, state: EmotionalState) -> Tuple[EmotionalState, dict]:
        """
        Update state with collapse detection.
        
        Args:
            state: Current emotional state
        
        Returns:
            (updated_state, diagnostics)
        """
        alpha = self.compute_alpha(state.E, state.m)
        prob = self.collapse_probability(alpha)
        is_collapsed = self.is_collapse(alpha, hard_threshold=False)
        
        state.alpha = alpha
        state.collapse_probability = prob
        
        diagnostics = {
            'alpha': alpha,
            'collapse_probability': prob,
            'is_collapsed': is_collapsed,
            'distance_to_threshold': alpha - self.alpha_c
        }
        
        return state, diagnostics
    
    def compute_stability_margin(self, E: float, m: float) -> float:
        """
        Compute how close state is to collapse.
        
        Returns negative if in danger, positive if stable.
        Distance = (α_c - α) * m
        """
        alpha = self.compute_alpha(E, m)
        margin = (self.alpha_c - alpha) * m
        return margin
    
    def time_to_collapse(self, E: float, m: float, dE_per_step: float) -> float:
        """
        Estimate steps until collapse if dE grows linearly.
        
        Args:
            E: Current energy
            m: Current mass
            dE_per_step: Energy growth per timestep
        
        Returns:
            Steps to collapse (inf if dE_per_step <= 0)
        """
        if dE_per_step <= 0:
            return float('inf')
        
        alpha = self.compute_alpha(E, m)
        if alpha >= self.alpha_c:
            return 0.0
        
        steps = (self.alpha_c * m - E) / dE_per_step
        return max(0.0, steps)
    
    def to_dict(self):
        """Serialize model parameters."""
        return {
            'alpha_c': self.alpha_c,
            'beta_0': self.beta_0,
            'beta_1': self.beta_1
        }
    
    @classmethod
    def from_dict(cls, data):
        """Deserialize model from parameters."""
        return cls(
            alpha_c=data.get('alpha_c', 1.5),
            beta_0=data.get('beta_0', -5.48),
            beta_1=data.get('beta_1', 3.20)
        )
