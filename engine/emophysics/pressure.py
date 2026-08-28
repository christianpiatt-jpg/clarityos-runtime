"""
Pressure Model: P = k(D*T)/N
Implements system-level pressure computation from dose, arousal, and narrative compression.
"""

from typing import Optional, Tuple
from .state import EmotionalState


class PressureModel:
    """
    Compute objective system pressure from inputs.
    
    Formula: P = B * (D * T) / N
    
    Where:
        B = basin coefficient (default 1.2)
        D = dose (intensity count)
        T = arousal/intensity (log-normal)
        N = narrative compression (5.0 typical)
    """
    
    def __init__(self, B: float = 1.2):
        """
        Initialize pressure model.
        
        Args:
            B: Basin coefficient controlling system sensitivity
        """
        self.B = B
    
    def compute(self, D: int, T: float, N: float) -> float:
        """
        Compute pressure for given inputs.
        
        Args:
            D: Dose (intensity count)
            T: Arousal (log-normal, typically 0.1-5.0)
            N: Narrative compression (typically 1-10)
        
        Returns:
            Pressure value (non-negative)
        """
        if N <= 0:
            return float('inf')
        
        P = self.B * (D * T) / N
        return max(0.0, P)
    
    def compute_elasticity(self, D: int, T: float, N: float) -> Tuple[float, float, float]:
        """
        Compute elasticities: how P responds to 1% changes in D, T, N.
        
        Expected elasticities from theory:
            dP/dD per 1% D change: ~1.0
            dP/dT per 1% T change: ~1.0
            dP/dN per 1% N change: ~-1.0
        
        Args:
            D: Current dose
            T: Current arousal
            N: Current narrative space
        
        Returns:
            (elastic_D, elastic_T, elastic_N)
        """
        if D == 0 or T <= 0 or N <= 0:
            return (0.0, 0.0, 0.0)
        
        # For P = B*D*T/N:
        # dP/dD = B*T/N
        # dP/dT = B*D/N
        # dP/dN = -B*D*T/N^2
        
        # Elasticity = (dP/dX) * (X/P)
        P = self.compute(D, T, N)
        
        if P == 0:
            return (0.0, 0.0, 0.0)
        
        elastic_D = (self.B * T / N) * (D / P)
        elastic_T = (self.B * D / N) * (T / P)
        elastic_N = (-self.B * D * T / (N ** 2)) * (N / P)
        
        return (elastic_D, elastic_T, elastic_N)
    
    def update_state(self, state: EmotionalState) -> EmotionalState:
        """
        Update state with computed pressure.
        
        Args:
            state: Current emotional state
        
        Returns:
            Updated state with P and P_perc set
        """
        P = self.compute(state.D, state.T, state.N)
        state.P = P
        state.P_perc = state.r * P
        return state
    
    def to_dict(self):
        """Serialize model parameters."""
        return {'B': self.B}
    
    @classmethod
    def from_dict(cls, data):
        """Deserialize model from parameters."""
        return cls(B=data.get('B', 1.2))
