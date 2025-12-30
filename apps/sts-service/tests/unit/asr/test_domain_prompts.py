"""
Unit tests for domain prompts.

TDD: These tests are written BEFORE implementation.
"""

import pytest


class TestGetDomainPrompt:
    """Tests for domain prompt generation."""

    def test_get_domain_prompt_sports(self):
        """Test sports domain prompt contains sports vocabulary."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt = get_domain_prompt("sports")

        # Should contain general sports terms
        assert len(prompt) > 0
        assert any(word in prompt.lower() for word in ["score", "goal", "game", "team", "play"])

    def test_get_domain_prompt_football(self):
        """Test football domain prompt contains NFL vocabulary."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt = get_domain_prompt("football")

        # Should contain NFL-specific terms
        assert len(prompt) > 0
        # Common football terms
        assert any(
            word in prompt.lower()
            for word in ["touchdown", "quarterback", "yards", "field goal", "mahomes", "chiefs"]
        )

    def test_get_domain_prompt_basketball(self):
        """Test basketball domain prompt contains NBA vocabulary."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt = get_domain_prompt("basketball")

        assert len(prompt) > 0
        # Common basketball terms
        assert any(word in prompt.lower() for word in ["three-pointer", "dunk", "rebound", "court"])

    def test_get_domain_prompt_news(self):
        """Test news domain prompt contains news vocabulary."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt = get_domain_prompt("news")

        assert len(prompt) > 0

    def test_get_domain_prompt_interview(self):
        """Test interview domain prompt."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt = get_domain_prompt("interview")

        assert len(prompt) > 0

    def test_get_domain_prompt_general(self):
        """Test general domain returns minimal/empty prompt."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt = get_domain_prompt("general")

        # General domain should have minimal or no prompt
        # (empty string is valid for no priming)
        assert isinstance(prompt, str)

    def test_get_domain_prompt_unknown_returns_general(self):
        """Test unknown domain falls back to general."""
        from sts_service.asr.domain_prompts import get_domain_prompt

        prompt_unknown = get_domain_prompt("unknown_domain_xyz")
        prompt_general = get_domain_prompt("general")

        assert prompt_unknown == prompt_general

    def test_domain_prompts_contain_vocabulary(self):
        """Test that domain prompts contain actual vocabulary words."""
        from sts_service.asr.domain_prompts import DOMAIN_PROMPTS

        for domain, prompt in DOMAIN_PROMPTS.items():
            if domain != "general":
                # Non-general prompts should have some content
                assert len(prompt.strip()) > 0, f"Domain {domain} has empty prompt"

    def test_domain_prompts_reasonable_length(self):
        """Test that domain prompts are reasonable length."""
        from sts_service.asr.domain_prompts import DOMAIN_PROMPTS

        for domain, prompt in DOMAIN_PROMPTS.items():
            # Prompts shouldn't be too long (Whisper has context limits)
            assert len(prompt) < 500, f"Domain {domain} prompt too long: {len(prompt)}"
