"""
Custom Exceptions for RealEstateRAG

도메인별 커스텀 예외 정의
"""


class RealEstateRAGError(Exception):
    """Base exception for RealEstateRAG"""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# ============================================================
# Ingestion Errors
# ============================================================

class IngestionError(RealEstateRAGError):
    """데이터 수집/처리 오류"""
    pass


class LoaderError(IngestionError):
    """데이터 로딩 오류"""
    pass


class ParsingError(IngestionError):
    """파싱 오류"""
    pass


class ValidationError(IngestionError):
    """유효성 검증 오류"""
    pass


class AnalysisError(IngestionError):
    """분석 파이프라인 오류"""
    pass


# ============================================================
# Graph Errors
# ============================================================

class GraphError(RealEstateRAGError):
    """그래프 관련 오류"""
    pass


class SchemaError(GraphError):
    """스키마 오류"""
    pass


class CypherError(GraphError):
    """Cypher 쿼리 오류"""
    
    def __init__(self, message: str, query: str = None, details: dict = None):
        super().__init__(message, details)
        self.query = query


class EntityNotFoundError(GraphError):
    """엔티티 미발견 오류"""
    
    def __init__(self, entity_type: str, entity_id: str):
        message = f"{entity_type} with ID '{entity_id}' not found"
        super().__init__(message, {"entity_type": entity_type, "entity_id": entity_id})


class DuplicateEntityError(GraphError):
    """중복 엔티티 오류"""
    
    def __init__(self, entity_type: str, entity_id: str):
        message = f"{entity_type} with ID '{entity_id}' already exists"
        super().__init__(message, {"entity_type": entity_type, "entity_id": entity_id})


# ============================================================
# Query Errors
# ============================================================

class QueryError(RealEstateRAGError):
    """쿼리 엔진 오류"""
    pass


class TranslationError(QueryError):
    """NL-to-Cypher 변환 오류"""
    
    def __init__(self, question: str, reason: str = None):
        message = f"Failed to translate query: {question}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, {"question": question, "reason": reason})


class RetrievalError(QueryError):
    """검색 오류"""
    pass


class SynthesisError(QueryError):
    """응답 생성 오류"""
    pass


# ============================================================
# Infrastructure Errors
# ============================================================

class InfrastructureError(RealEstateRAGError):
    """인프라 관련 오류"""
    pass


class DatabaseConnectionError(InfrastructureError):
    """데이터베이스 연결 오류"""
    pass


class LLMError(InfrastructureError):
    """LLM 서비스 오류"""
    pass


class LLMTimeoutError(LLMError):
    """LLM 타임아웃 오류"""
    pass


class LLMRateLimitError(LLMError):
    """LLM Rate Limit 오류"""
    pass


class StorageError(InfrastructureError):
    """스토리지 오류"""
    pass


class FileNotFoundError(StorageError):
    """파일 미발견 오류"""
    pass


# ============================================================
# Configuration Errors
# ============================================================

class ConfigurationError(RealEstateRAGError):
    """설정 오류"""
    pass


class MissingConfigError(ConfigurationError):
    """필수 설정 미존재 오류"""
    
    def __init__(self, config_key: str):
        message = f"Missing required configuration: {config_key}"
        super().__init__(message, {"config_key": config_key})
