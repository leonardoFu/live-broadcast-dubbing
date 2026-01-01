"""
Contract tests for AudioAsset schema validation.

Tests that AudioAsset JSON serialization matches the expected schema
and validates the TTS pipeline contract.

Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 100% of schema fields.
"""

import json

import pytest
from sts_service.tts.errors import TTSError, TTSErrorType
from sts_service.tts.models import (
    AudioAsset,
    AudioFormat,
    AudioStatus,
)


class TestAudioAssetSchema:
    """Contract tests for AudioAsset JSON schema compliance."""

    @pytest.fixture
    def valid_audio_asset(self):
        """Create a valid AudioAsset for schema testing."""
        return AudioAsset(
            stream_id="stream-abc",
            sequence_number=42,
            parent_asset_ids=["text-uuid-123"],
            component_instance="coqui-xtts-v2",
            audio_format=AudioFormat.PCM_F32LE,
            sample_rate_hz=16000,
            channels=1,
            duration_ms=2000,
            payload_ref="mem://fragments/stream-abc/42",
            language="en",
            status=AudioStatus.SUCCESS,
            processing_time_ms=1850,
            voice_cloning_used=False,
            preprocessed_text="Hello world!",
        )

    def test_audio_asset_json_serialization(self, valid_audio_asset):
        """Test AudioAsset JSON serialization produces valid JSON."""
        json_str = valid_audio_asset.model_dump_json()
        parsed = json.loads(json_str)

        # Verify required fields are present
        assert "asset_id" in parsed
        assert "stream_id" in parsed
        assert "sequence_number" in parsed
        assert "component" in parsed
        assert "component_instance" in parsed
        assert "audio_format" in parsed
        assert "sample_rate_hz" in parsed
        assert "channels" in parsed
        assert "duration_ms" in parsed
        assert "payload_ref" in parsed
        assert "language" in parsed
        assert "status" in parsed

    def test_audio_asset_parent_asset_ids_linkage(self, valid_audio_asset):
        """Test parent_asset_ids links to TextAsset correctly."""
        json_data = valid_audio_asset.model_dump()

        assert "parent_asset_ids" in json_data
        assert isinstance(json_data["parent_asset_ids"], list)
        assert len(json_data["parent_asset_ids"]) > 0
        assert "text-uuid-123" in json_data["parent_asset_ids"]

    def test_audio_asset_lineage_tracking(self, valid_audio_asset):
        """Test asset lineage tracking (component, component_instance)."""
        json_data = valid_audio_asset.model_dump()

        # Component should always be 'tts'
        assert json_data["component"] == "tts"

        # component_instance should identify the provider
        assert "component_instance" in json_data
        assert len(json_data["component_instance"]) > 0

        # Asset should have unique ID
        assert "asset_id" in json_data
        assert len(json_data["asset_id"]) > 0

        # Created timestamp should be present
        assert "created_at" in json_data

    def test_audio_asset_status_values(self):
        """Test AudioAsset status field accepts valid enum values."""
        base_data = {
            "stream_id": "stream-abc",
            "sequence_number": 1,
            "parent_asset_ids": ["text-uuid"],
            "component_instance": "test",
            "audio_format": AudioFormat.PCM_F32LE,
            "sample_rate_hz": 16000,
            "channels": 1,
            "duration_ms": 1000,
            "payload_ref": "mem://test",
            "language": "en",
        }

        # Test all valid status values
        for status in [AudioStatus.SUCCESS, AudioStatus.PARTIAL, AudioStatus.FAILED]:
            asset = AudioAsset(**base_data, status=status)
            assert asset.status == status

    def test_audio_asset_with_errors_schema(self):
        """Test AudioAsset with errors has correct schema."""
        error = TTSError(
            error_type=TTSErrorType.MODEL_LOAD_FAILED,
            message="Model not found",
            retryable=True,
            details={"model_path": "/models/test"},
        )

        asset = AudioAsset(
            stream_id="stream-abc",
            sequence_number=1,
            parent_asset_ids=["text-uuid"],
            component_instance="test",
            audio_format=AudioFormat.PCM_F32LE,
            sample_rate_hz=16000,
            channels=1,
            duration_ms=0,
            payload_ref="",
            language="en",
            status=AudioStatus.FAILED,
            errors=[error],
        )

        json_data = asset.model_dump()

        # Verify errors field structure
        assert "errors" in json_data
        assert isinstance(json_data["errors"], list)
        assert len(json_data["errors"]) == 1

        error_data = json_data["errors"][0]
        assert "error_type" in error_data
        assert "message" in error_data
        assert "retryable" in error_data

    def test_audio_asset_processing_metadata_schema(self, valid_audio_asset):
        """Test processing metadata fields in schema."""
        json_data = valid_audio_asset.model_dump()

        # Optional processing metadata
        assert "processing_time_ms" in json_data
        assert "voice_cloning_used" in json_data
        assert "preprocessed_text" in json_data

    def test_audio_asset_round_trip_serialization(self, valid_audio_asset):
        """Test AudioAsset can be serialized and deserialized."""
        # Serialize to JSON
        json_str = valid_audio_asset.model_dump_json()

        # Deserialize back
        restored = AudioAsset.model_validate_json(json_str)

        # Verify key fields match
        assert restored.stream_id == valid_audio_asset.stream_id
        assert restored.sequence_number == valid_audio_asset.sequence_number
        assert restored.component == valid_audio_asset.component
        assert restored.audio_format == valid_audio_asset.audio_format
        assert restored.sample_rate_hz == valid_audio_asset.sample_rate_hz
        assert restored.channels == valid_audio_asset.channels
        assert restored.duration_ms == valid_audio_asset.duration_ms
        assert restored.status == valid_audio_asset.status

    def test_audio_asset_sample_rate_schema(self):
        """Test sample_rate_hz in schema accepts valid rates."""
        base_data = {
            "stream_id": "stream-abc",
            "sequence_number": 1,
            "parent_asset_ids": ["text-uuid"],
            "component_instance": "test",
            "audio_format": AudioFormat.PCM_F32LE,
            "channels": 1,
            "duration_ms": 1000,
            "payload_ref": "mem://test",
            "language": "en",
            "status": AudioStatus.SUCCESS,
        }

        valid_rates = [8000, 16000, 22050, 24000, 44100, 48000]
        for rate in valid_rates:
            asset = AudioAsset(**base_data, sample_rate_hz=rate)
            json_data = asset.model_dump()
            assert json_data["sample_rate_hz"] == rate


class TestTTSMetricsSchema:
    """Contract tests for TTSMetrics JSON schema compliance."""

    def test_tts_metrics_json_serialization(self):
        """Test TTSMetrics JSON serialization produces valid JSON."""
        from sts_service.tts.models import TTSMetrics

        metrics = TTSMetrics(
            stream_id="stream-abc",
            sequence_number=42,
            asset_id="audio-uuid-456",
            preprocess_time_ms=5,
            synthesis_time_ms=1645,
            alignment_time_ms=200,
            total_time_ms=1850,
            baseline_duration_ms=2500,
            target_duration_ms=2000,
            final_duration_ms=2000,
            speed_factor_applied=1.25,
            speed_factor_clamped=False,
            model_used="xtts_v2",
            voice_cloning_active=False,
            fast_mode_active=False,
        )

        json_str = metrics.model_dump_json()
        parsed = json.loads(json_str)

        # Verify timing fields
        assert "preprocess_time_ms" in parsed
        assert "synthesis_time_ms" in parsed
        assert "alignment_time_ms" in parsed
        assert "total_time_ms" in parsed

        # Verify duration matching fields
        assert "baseline_duration_ms" in parsed
        assert "target_duration_ms" in parsed
        assert "final_duration_ms" in parsed
        assert "speed_factor_applied" in parsed
        assert "speed_factor_clamped" in parsed

        # Verify model info
        assert "model_used" in parsed
        assert "voice_cloning_active" in parsed
        assert "fast_mode_active" in parsed
