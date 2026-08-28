"""
State management for Emotional Physics
Unified state object tracking E, m, r, N, T, D

Vendored from ClarityOS_Library 2026-08-28 (engine/emophysics v1.0.0).
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class EmotionalState:
    """
    Unified state representation for Emotional Physics model.
    
    Attributes:
        E (float): Emotional energy
        m (float): Identity mass
        r (float): Relational registration (0.6 to 1.4 typical)
        N (float): Narrative compression space
        D (int): Dose (intensity count)
        T (float): Arousal/intensity (log-normal distributed)
        alpha (float): Collapse ratio E/m
        P (float): Objective pressure. ★ NOT AN ORDINARY ATTRIBUTE -- it
            does NOT exist until a PressureModel writes it. Accessing
            ``state.P`` on a fresh state raises AttributeError.

            ★★ THIS IS DELIBERATE AND MUST STAY THAT WAY. RelationalModel
            .update_state (relational.py:112) tests ``hasattr(state, 'P')``
            and returns {'error': 'State missing P value'} when it is
            absent. Giving P a default of 0.0 would make that guard
            permanently unreachable and turn a loud error into a plausible
            zero -- P_perc = r * 0.0 -- on a state whose pressure was never
            computed. The absence IS the signal.

            Vendored into ClarityOS_Code 2026-08-28: the docstring was
            corrected rather than the field, because defaulting the field
            would have silently deleted an error path.
            Use ``hasattr(state, 'P')`` or ``to_dict()['P']`` (which
            defaults to 0.0 for serialization only).
        P_perc (float): Perceived pressure (r * P)
        collapse_probability (float): Probability of collapse (0-1)
        timestamp (datetime): When state was recorded
        metadata (dict): Additional context
    """
    
    E: float = 0.5
    m: float = 3.0
    r: float = 1.0
    N: float = 5.0
    D: int = 0
    T: float = 0.5
    
    alpha: float = field(init=False)
    P: float = field(init=False)
    P_perc: float = field(init=False)
    collapse_probability: float = field(init=False, default=0.0)
    
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Compute derived fields after initialization."""
        self.alpha = self.E / self.m if self.m > 0 else float('inf')
        self.P_perc = self.r * self.P if hasattr(self, 'P') else 0.0
    
    def update(self, E: Optional[float] = None, m: Optional[float] = None,
               r: Optional[float] = None, N: Optional[float] = None,
               D: Optional[int] = None, T: Optional[float] = None,
               P: Optional[float] = None):
        """Update state values and recompute derived fields."""
        if E is not None:
            self.E = max(0.0, E)
        if m is not None:
            self.m = max(0.1, m)
        if r is not None:
            self.r = max(0.1, r)
        if N is not None:
            self.N = max(0.5, N)
        if D is not None:
            self.D = max(0, D)
        if T is not None:
            self.T = max(0.0, T)
        if P is not None:
            self.P = max(0.0, P)
        
        self.timestamp = datetime.now()
        self._recompute_derived()
    
    def _recompute_derived(self):
        """Recompute all derived fields."""
        self.alpha = self.E / self.m if self.m > 0 else float('inf')
        if hasattr(self, 'P'):
            self.P_perc = self.r * self.P
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary."""
        return {
            'E': self.E,
            'm': self.m,
            'r': self.r,
            'N': self.N,
            'D': self.D,
            'T': self.T,
            'alpha': self.alpha,
            'P': getattr(self, 'P', 0.0),
            'P_perc': self.P_perc,
            'collapse_probability': self.collapse_probability,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmotionalState':
        """Create state from dictionary."""
        state = cls(
            E=data.get('E', 0.5),
            m=data.get('m', 3.0),
            r=data.get('r', 1.0),
            N=data.get('N', 5.0),
            D=data.get('D', 0),
            T=data.get('T', 0.5)
        )
        if 'P' in data:
            state.P = data['P']
        if 'collapse_probability' in data:
            state.collapse_probability = data['collapse_probability']
        if 'metadata' in data:
            state.metadata = data['metadata']
        state._recompute_derived()
        return state
