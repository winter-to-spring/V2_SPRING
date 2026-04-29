"""
Tests for triage_pipeline module.

Verifies:
1. Module structure and imports
2. State schema compliance
3. Node functionality (classify, summarize, hash_embed)
4. Fallback behavior when OPENAI_API_KEY is unavailable
5. Deterministic heuristics (critical keywords, mentions, channel priority)
6. MD5 hash consistency
"""

import hashlib
import os
import pytest

# Ensure no API key is set for deterministic offline testing
os.environ.pop("OPENAI_API_KEY", None)

from test.service_backend.app.services.triage_pipeline import (
    TriageLevel,
    ChannelPriority,
    TriageState,
    run_triage,
    _classify_with_fallback,
    _hash_embed_node,
    _summarize_node,
)


class TestTriageLevels:
    """Test TriageLevel enum."""
    
    def test_triage_level_values(self):
        """Verify TriageLevel enum has expected values."""
        assert TriageLevel.CRITICAL == "critical"
        assert TriageLevel.HIGH == "high"
        assert TriageLevel.MEDIUM == "medium"
        assert TriageLevel.LOW == "low"
    
    def test_channel_priority_values(self):
        """Verify ChannelPriority enum has expected values."""
        assert ChannelPriority.CRITICAL == "critical"
        assert ChannelPriority.HIGH == "high"
        assert ChannelPriority.MEDIUM == "medium"
        assert ChannelPriority.LOW == "low"


class TestClassifyWithFallback:
    """Test fallback classification logic."""
    
    def test_classify_critical_at_channel(self):
        """@channel keyword should trigger critical."""
        level = _classify_with_fallback("@channel please review", "low")
        assert level == TriageLevel.CRITICAL
    
    def test_classify_critical_urgent(self):
        """'urgent' keyword should trigger critical."""
        level = _classify_with_fallback("This is urgent", "low")
        assert level == TriageLevel.CRITICAL
    
    def test_classify_critical_asap(self):
        """'asap' keyword should trigger critical."""
        level = _classify_with_fallback("Fix this asap", "low")
        assert level == TriageLevel.CRITICAL
    
    def test_classify_critical_keyword(self):
        """'critical' keyword should trigger critical."""
        level = _classify_with_fallback("Critical issue found", "low")
        assert level == TriageLevel.CRITICAL
    
    def test_classify_high_mention(self):
        """Mention of user (@username) should be high."""
        level = _classify_with_fallback("@alice can you help?", "low")
        assert level == TriageLevel.HIGH
    
    def test_classify_high_alert(self):
        """'alert' keyword should be high."""
        level = _classify_with_fallback("System alert triggered", "low")
        assert level == TriageLevel.HIGH
    
    def test_classify_fallback_channel_priority_critical(self):
        """Channel priority 'critical' should be returned when no keywords match."""
        level = _classify_with_fallback("Regular message", "critical")
        assert level == "critical"
    
    def test_classify_fallback_channel_priority_high(self):
        """Channel priority 'high' should be returned when no keywords match."""
        level = _classify_with_fallback("Regular message", "high")
        assert level == "high"
    
    def test_classify_fallback_default_low(self):
        """Default to low when no indicators present."""
        level = _classify_with_fallback("Just a normal message", "low")
        assert level == TriageLevel.LOW
    
    def test_classify_case_insensitive(self):
        """Classification should be case-insensitive."""
        level_upper = _classify_with_fallback("@CHANNEL issue", "low")
        level_lower = _classify_with_fallback("@channel issue", "low")
        assert level_upper == level_lower == TriageLevel.CRITICAL


class TestHashEmbedNode:
    """Test hash_embed node functionality."""
    
    def test_hash_embed_md5_consistency(self):
        """MD5 hash should be consistent for same input."""
        text = "Test message for hashing"
        expected_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        
        state: TriageState = {
            "raw_text": text,
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "Test",
            "embedding_hash": "",
        }
        
        result = _hash_embed_node(state)
        assert result["embedding_hash"] == expected_hash
    
    def test_hash_embed_hex_format(self):
        """Embedding hash should be valid hex string."""
        state: TriageState = {
            "raw_text": "Test",
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "Test",
            "embedding_hash": "",
        }
        
        result = _hash_embed_node(state)
        # Valid hex string of length 32 (MD5 hex digest)
        assert len(result["embedding_hash"]) == 32
        assert all(c in "0123456789abcdef" for c in result["embedding_hash"])
    
    def test_hash_embed_different_texts(self):
        """Different texts should produce different hashes."""
        state1: TriageState = {
            "raw_text": "Text A",
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "",
            "embedding_hash": "",
        }
        state2: TriageState = {
            "raw_text": "Text B",
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "",
            "embedding_hash": "",
        }
        
        result1 = _hash_embed_node(state1)
        result2 = _hash_embed_node(state2)
        assert result1["embedding_hash"] != result2["embedding_hash"]


class TestSummarizeNode:
    """Test summarize node functionality."""
    
    def test_summarize_fallback_single_sentence(self):
        """Summarize should handle single sentence fallback."""
        state: TriageState = {
            "raw_text": "This is a test message.",
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "",
            "embedding_hash": "",
        }
        
        result = _summarize_node(state)
        assert result["summary"]
        assert len(result["summary"]) > 0
    
    def test_summarize_fallback_multisentence(self):
        """Summarize should extract first sentence."""
        state: TriageState = {
            "raw_text": "First sentence. Second sentence. Third sentence.",
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "",
            "embedding_hash": "",
        }
        
        result = _summarize_node(state)
        assert "First sentence" in result["summary"]
    
    def test_summarize_truncation(self):
        """Summarize should truncate very long single sentences."""
        long_text = "A" * 200
        state: TriageState = {
            "raw_text": long_text,
            "channel_priority": "low",
            "triage_level": "low",
            "summary": "",
            "embedding_hash": "",
        }
        
        result = _summarize_node(state)
        assert len(result["summary"]) <= 150


class TestRunTriage:
    """Test async run_triage entry point."""
    
    @pytest.mark.asyncio
    async def test_run_triage_basic(self):
        """Test basic triage run with default channel priority."""
        result = await run_triage("@channel urgent issue", "critical")
        
        assert isinstance(result, dict)
        assert "raw_text" in result
        assert "channel_priority" in result
        assert "triage_level" in result
        assert "summary" in result
        assert "embedding_hash" in result
    
    @pytest.mark.asyncio
    async def test_run_triage_critical_detection(self):
        """Test that critical keywords are detected."""
        result = await run_triage("@channel critical issue", "low")
        
        assert result["triage_level"] == TriageLevel.CRITICAL
        assert result["raw_text"] == "@channel critical issue"
        assert result["channel_priority"] == "low"
    
    @pytest.mark.asyncio
    async def test_run_triage_high_detection(self):
        """Test that high-priority keywords are detected."""
        result = await run_triage("@alice important update", "low")
        
        assert result["triage_level"] == TriageLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_run_triage_low_default(self):
        """Test that normal message defaults to low."""
        result = await run_triage("Just a normal message", "low")
        
        assert result["triage_level"] == TriageLevel.LOW
    
    @pytest.mark.asyncio
    async def test_run_triage_has_summary(self):
        """Test that summary is generated."""
        result = await run_triage("This is a test message for summarization.", "low")
        
        assert result["summary"]
        assert len(result["summary"]) > 0
    
    @pytest.mark.asyncio
    async def test_run_triage_has_hash(self):
        """Test that embedding hash is generated."""
        result = await run_triage("Test message", "low")
        
        assert result["embedding_hash"]
        assert len(result["embedding_hash"]) == 32
        assert all(c in "0123456789abcdef" for c in result["embedding_hash"])
    
    @pytest.mark.asyncio
    async def test_run_triage_deterministic(self):
        """Test that triage is deterministic for same input."""
        text = "Sample message for testing"
        
        result1 = await run_triage(text, "medium")
        result2 = await run_triage(text, "medium")
        
        assert result1["triage_level"] == result2["triage_level"]
        assert result1["embedding_hash"] == result2["embedding_hash"]
    
    @pytest.mark.asyncio
    async def test_run_triage_default_channel_priority(self):
        """Test default channel priority."""
        result = await run_triage("Test message")
        
        assert result["channel_priority"] == "low"
    
    @pytest.mark.asyncio
    async def test_run_triage_state_schema(self):
        """Test that all required state fields are present."""
        result = await run_triage("Test", "high")
        
        required_keys = {"raw_text", "channel_priority", "triage_level", "summary", "embedding_hash"}
        assert required_keys.issubset(set(result.keys()))
    
    @pytest.mark.asyncio
    async def test_run_triage_preserves_input(self):
        """Test that raw_text and channel_priority are preserved."""
        text = "Original message text"
        priority = "high"
        
        result = await run_triage(text, priority)
        
        assert result["raw_text"] == text
        assert result["channel_priority"] == priority


class TestOfflineFallback:
    """Test offline fallback when no API key."""
    
    def test_no_api_key_environment(self):
        """Verify OPENAI_API_KEY is not set in test environment."""
        assert not os.getenv("OPENAI_API_KEY", "").strip()
    
    @pytest.mark.asyncio
    async def test_pipeline_works_offline(self):
        """Test that entire pipeline works without API key."""
        result = await run_triage("@channel urgent: system down", "medium")
        
        assert result["triage_level"] == TriageLevel.CRITICAL
        assert result["summary"]
        assert result["embedding_hash"]
        assert len(result["embedding_hash"]) == 32


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_text(self):
        """Test handling of empty text."""
        result = await run_triage("", "low")
        
        assert result["raw_text"] == ""
        assert result["triage_level"] == TriageLevel.LOW
    
    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        """Test handling of whitespace-only text."""
        result = await run_triage("   ", "low")
        
        assert result["triage_level"] == TriageLevel.LOW
    
    @pytest.mark.asyncio
    async def test_very_long_text(self):
        """Test handling of very long text."""
        long_text = "A" * 10000
        result = await run_triage(long_text, "low")
        
        assert result["raw_text"] == long_text
        assert result["embedding_hash"]
    
    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test handling of special characters."""
        text = "Test @#$%^&*() special chars"
        result = await run_triage(text, "low")
        
        assert result["raw_text"] == text
        assert result["embedding_hash"]
    
    @pytest.mark.asyncio
    async def test_unicode_text(self):
        """Test handling of unicode text."""
        text = "Test with emoji 🚨 and unicode: café"
        result = await run_triage(text, "low")
        
        assert result["raw_text"] == text
        assert result["embedding_hash"]


class TestModuleStructure:
    """Test module imports and structure."""
    
    def test_module_imports(self):
        """Verify key exports are available."""
        from test.service_backend.app.services import triage_pipeline
        
        assert hasattr(triage_pipeline, "TriageLevel")
        assert hasattr(triage_pipeline, "ChannelPriority")
        assert hasattr(triage_pipeline, "TriageState")
        assert hasattr(triage_pipeline, "run_triage")
    
    def test_triage_state_is_typeddict(self):
        """Verify TriageState is a TypedDict."""
        from typing import get_type_hints
        
        hints = get_type_hints(TriageState)
        assert "raw_text" in hints
        assert "channel_priority" in hints
        assert "triage_level" in hints
        assert "summary" in hints
        assert "embedding_hash" in hints
