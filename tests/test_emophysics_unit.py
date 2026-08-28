"""
Unit tests for Emotional Physics engine modules
"""

import pytest
# ★ numpy import removed at vendoring: this file imported it and used it
# ZERO times -- the same dead-import pattern found in threshold.py and
# pressure.py. ClarityOS_Code does not ship numpy; leaving it here would
# have made the whole suite uncollectable for no benefit.
from engine.emophysics import (
    EmotionalState, PressureModel, ConversionModel, 
    ThresholdModel, RelationalModel
)


class TestEmotionalState:
    """Test state management."""
    
    def test_state_creation(self):
        """Test creating a state."""
        state = EmotionalState(E=1.0, m=2.0, r=1.1)
        assert state.E == 1.0
        assert state.m == 2.0
        assert state.alpha == 0.5
    
    def test_state_update(self):
        """Test updating state values."""
        state = EmotionalState()
        state.update(E=2.0, m=4.0)
        assert state.E == 2.0
        assert state.m == 4.0
        assert state.alpha == 0.5
    
    def test_state_serialization(self):
        """Test to_dict and from_dict."""
        state = EmotionalState(E=1.5, m=3.0)
        state.P = 2.0
        data = state.to_dict()
        
        state2 = EmotionalState.from_dict(data)
        assert state2.E == 1.5
        assert state2.m == 3.0


class TestPressureModel:
    """Test pressure computation."""
    
    def test_basic_computation(self):
        """Test P = B*D*T/N."""
        model = PressureModel(B=1.2)
        P = model.compute(D=5, T=2.0, N=5.0)
        expected = 1.2 * 5 * 2.0 / 5.0
        assert abs(P - expected) < 1e-6
    
    def test_elasticity(self):
        """Test elasticity computation."""
        model = PressureModel(B=1.2)
        e_D, e_T, e_N = model.compute_elasticity(D=5, T=2.0, N=5.0)
        
        # Elasticities should be close to [1, 1, -1]
        assert abs(e_D - 1.0) < 0.05
        assert abs(e_T - 1.0) < 0.05
        assert abs(e_N - (-1.0)) < 0.05
    
    def test_state_update(self):
        """Test updating state with pressure."""
        model = PressureModel()
        state = EmotionalState(D=3, T=1.5, N=5.0)
        state = model.update_state(state)
        
        assert hasattr(state, 'P')
        assert state.P > 0
        assert state.P_perc == state.r * state.P


class TestConversionModel:
    """Test energy conversion."""
    
    def test_delta_E_computation(self):
        """Test energy change calculation."""
        model = ConversionModel(C2=2.0, lam=0.5, gamma=0.3)
        delta_E = model.compute_delta_E(E=1.0, D=5, T=2.0, delta_m=0.1)
        
        # Expected: 0.5*5*2.0 - 0.3*1.0 + 2.0*0.1
        expected = 0.5*5*2.0 - 0.3*1.0 + 2.0*0.1
        assert abs(delta_E - expected) < 1e-6
    
    def test_state_update(self):
        """Test updating state with conversion."""
        model = ConversionModel()
        state = EmotionalState(E=1.0, m=2.0, D=3, T=1.5)
        state, diag = model.update_state(state, delta_m=0.2)
        
        assert state.E >= 0.0
        assert state.m > 0.0
        assert 'delta_E' in diag


class TestThresholdModel:
    """Test collapse detection."""
    
    def test_alpha_computation(self):
        """Test α = E/m."""
        model = ThresholdModel()
        alpha = model.compute_alpha(E=2.0, m=1.0)
        assert alpha == 2.0
    
    def test_hard_threshold(self):
        """Test hard collapse threshold."""
        model = ThresholdModel(alpha_c=1.5)
        
        assert not model.is_collapse(alpha=1.0, hard_threshold=True)
        assert model.is_collapse(alpha=2.0, hard_threshold=True)
    
    def test_collapse_probability(self):
        """Test logistic collapse probability."""
        model = ThresholdModel()
        prob_low = model.collapse_probability(alpha=0.5)
        prob_high = model.collapse_probability(alpha=2.5)
        
        assert 0 <= prob_low <= 1
        assert 0 <= prob_high <= 1
        assert prob_high > prob_low  # higher α → higher collapse prob
    
    def test_stability_margin(self):
        """Test stability margin calculation."""
        model = ThresholdModel(alpha_c=1.5)
        
        # Below threshold: positive margin
        margin_safe = model.compute_stability_margin(E=1.0, m=1.0)
        assert margin_safe > 0
        
        # Above threshold: negative margin
        margin_danger = model.compute_stability_margin(E=3.0, m=1.0)
        assert margin_danger < 0


class TestRelationalModel:
    """Test relational filtering."""
    
    def test_perceived_pressure(self):
        """Test P_perc = r*P."""
        model = RelationalModel()
        P_perc = model.compute_perceived_pressure(P=2.0, r=1.5, noise=False)
        assert abs(P_perc - 3.0) < 1e-6
    
    def test_resilience(self):
        """Test resilience computation."""
        model = RelationalModel()
        
        # r < 1 → high resilience
        resilience_good = model.relational_resilience(r=0.8)
        assert resilience_good > 1.0
        
        # r > 1 → low resilience
        resilience_bad = model.relational_resilience(r=1.2)
        assert resilience_bad < 1.0
    
    def test_registration_estimation(self):
        """Test estimating r from observations."""
        model = RelationalModel()
        r_est = model.estimate_relational_registration(P_perc=3.0, P=2.0)
        assert abs(r_est - 1.5) < 1e-6


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
