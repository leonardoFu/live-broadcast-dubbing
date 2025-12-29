"""
Unit tests for confidence mapping.

TDD: These tests are written BEFORE implementation.
"""

import pytest


class TestCalculateConfidence:
    """Tests for confidence score calculation from log probabilities."""

    def test_calculate_confidence_high_logprob(self):
        """Test high log probability maps to high confidence."""
        from sts_service.asr.confidence import calculate_confidence

        # Log prob close to 0 = high confidence
        result = calculate_confidence(avg_logprob=-0.1)

        assert result > 0.8
        assert result <= 1.0

    def test_calculate_confidence_low_logprob(self):
        """Test low log probability maps to low confidence."""
        from sts_service.asr.confidence import calculate_confidence

        # Very negative log prob = low confidence
        result = calculate_confidence(avg_logprob=-1.5)

        assert result < 0.5
        assert result >= 0.0

    def test_calculate_confidence_zero_logprob(self):
        """Test zero log probability maps to maximum confidence."""
        from sts_service.asr.confidence import calculate_confidence

        # Log prob of 0 = probability of 1.0 = perfect confidence
        result = calculate_confidence(avg_logprob=0.0)

        assert result == 1.0

    def test_calculate_confidence_negative_one_logprob(self):
        """Test log prob of -1.0 maps to moderate confidence."""
        from sts_service.asr.confidence import calculate_confidence

        # Using formula: clamp((avg_logprob + 1.0) / 1.0, 0, 1)
        # (-1.0 + 1.0) / 1.0 = 0.0
        result = calculate_confidence(avg_logprob=-1.0)

        assert result == pytest.approx(0.0, abs=0.01)

    def test_calculate_confidence_clamps_to_zero(self):
        """Test that very negative log prob clamps to 0."""
        from sts_service.asr.confidence import calculate_confidence

        # Very negative log prob should clamp to 0
        result = calculate_confidence(avg_logprob=-5.0)

        assert result == 0.0

    def test_calculate_confidence_clamps_to_one(self):
        """Test that positive log prob clamps to 1."""
        from sts_service.asr.confidence import calculate_confidence

        # Positive log prob (shouldn't happen but handle it)
        result = calculate_confidence(avg_logprob=0.5)

        assert result == 1.0

    def test_calculate_confidence_linear_mapping(self):
        """Test linear mapping in the valid range."""
        from sts_service.asr.confidence import calculate_confidence

        # Test linear relationship
        # Formula: clamp((avg_logprob + 1.0) / 1.0, 0, 1)
        # At -0.5: (-0.5 + 1.0) / 1.0 = 0.5
        result = calculate_confidence(avg_logprob=-0.5)

        assert result == pytest.approx(0.5, abs=0.01)
