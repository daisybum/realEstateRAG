"""
Unit Tests for Ingestion Module
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from realestaterag.ingestion.loaders.multimodal_loader import MultimodalLoader, MultimodalData
from realestaterag.ingestion.analyzers.qwen_analyzer import QwenAnalyzer, AnalysisStageResult
from realestaterag.ingestion.pipeline import IngestionPipeline


class TestMultimodalData:
    """MultimodalData 테스트"""
    
    def test_has_images(self):
        data = MultimodalData(
            report_id="test",
            text_content="content",
            images=[b"image1"],
            image_paths=["/path/img.png"],
            metadata={}
        )
        assert data.has_images is True
        assert data.image_count == 1
    
    def test_no_images(self):
        data = MultimodalData(
            report_id="test",
            text_content="content",
            images=[],
            image_paths=[],
            metadata={}
        )
        assert data.has_images is False


class TestMultimodalLoader:
    """MultimodalLoader 테스트"""
    
    def test_supported_extensions(self):
        loader = MultimodalLoader()
        assert ".txt" in loader.SUPPORTED_TEXT_EXTENSIONS
        assert ".png" in loader.SUPPORTED_IMAGE_EXTENSIONS
    
    def test_encode_image_base64(self):
        loader = MultimodalLoader()
        image_bytes = b"test image content"
        encoded = loader.encode_image_base64(image_bytes)
        assert isinstance(encoded, str)
        assert len(encoded) > 0
    
    def test_prepare_for_llm(self):
        loader = MultimodalLoader()
        data = MultimodalData(
            report_id="test",
            text_content="text",
            images=[b"img"],
            image_paths=["/path/img.png"],
            metadata={"key": "value"}
        )
        prepared = loader.prepare_for_llm(data)
        assert "text" in prepared
        assert "images" in prepared
        assert len(prepared["images"]) == 1


class TestAnalysisStageResult:
    """AnalysisStageResult 테스트"""
    
    def test_success_result(self):
        result = AnalysisStageResult(
            stage="fact_extraction",
            content='{"data": "test"}',
            raw_response='```json\n{"data": "test"}\n```',
            tokens_used=100,
            success=True
        )
        assert result.success is True
        assert result.error is None
    
    def test_failure_result(self):
        result = AnalysisStageResult(
            stage="test",
            content="",
            raw_response="",
            success=False,
            error="Timeout"
        )
        assert result.success is False
        assert result.error == "Timeout"


class TestQwenAnalyzer:
    """QwenAnalyzer 테스트"""
    
    def test_clean_json_code_block(self):
        analyzer = QwenAnalyzer()
        text = '```json\n{"key": "value"}\n```'
        result = analyzer._clean_json(text)
        assert result == '{"key": "value"}'
    
    def test_clean_json_plain(self):
        analyzer = QwenAnalyzer()
        text = '{"key": "value"}'
        result = analyzer._clean_json(text)
        assert result == '{"key": "value"}'


class TestIngestionPipeline:
    """IngestionPipeline 테스트"""
    
    def test_calculate_confidence(self):
        pipeline = IngestionPipeline()
        
        results = {
            "stage1": AnalysisStageResult("s1", "", "", success=True),
            "stage2": AnalysisStageResult("s2", "", "", success=True),
            "stage3": AnalysisStageResult("s3", "", "", success=False),
        }
        confidence = pipeline._calculate_confidence(results)
        assert confidence == pytest.approx(2/3, rel=0.01)
    
    def test_extract_entities(self, sample_fact_extraction):
        pipeline = IngestionPipeline()
        entities = pipeline._extract_entities(sample_fact_extraction)
        
        assert len(entities) >= 1
        district_entity = next(e for e in entities if e["type"] == "District")
        assert district_entity["name"] == "수지구"
    
    def test_extract_relationships(self, sample_fact_extraction):
        pipeline = IngestionPipeline()
        relationships = pipeline._extract_relationships(sample_fact_extraction)
        
        assert len(relationships) >= 1
        assert all(r["type"] == "LOCATED_IN" for r in relationships)
