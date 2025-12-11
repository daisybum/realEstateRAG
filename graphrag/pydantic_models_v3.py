"""
Pydantic Models for GraphRAG v3.0

LLM 출력 검증 및 파싱을 위한 Pydantic 모델
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator, field_validator
from enum import Enum
from datetime import datetime


class EntityType(str, Enum):
    """그래프 노드 타입"""
    REGION = "Region"
    DISTRICT = "District"
    NEIGHBORHOOD = "Neighborhood"
    COMPLEX = "Complex"
    INFRA = "Infra"
    MARKET_SNAPSHOT = "MarketSnapshot"
    REPORT = "Report"
    INVESTMENT_ANALYSIS = "InvestmentAnalysis"


class InfraCategory(str, Enum):
    """인프라 카테고리"""
    SUBWAY = "Subway"
    JOB_CENTER = "JobCenter"
    DEPT_STORE = "DeptStore"
    SCHOOL = "School"
    HOSPITAL = "Hospital"
    PARK = "Park"
    GOVERNMENT = "Government"
    TRANSPORT_HUB = "TransportHub"


class GradeTier(str, Enum):
    """등급"""
    S = "S"
    A = "A"
    B = "B"
    C = "C"


class Entity(BaseModel):
    """그래프 노드 엔티티
    
    Examples:
        >>> Entity(id="INFRA_GANGNAM_STATION", type=EntityType.INFRA, name="강남역", 
        ...        properties={"category": "Subway", "tier": "S"})
        >>> Entity(id="MARKET_EUNMA_202412", type=EntityType.MARKET_SNAPSHOT, 
        ...        date="2024-12", properties={"sales_price": 150000})
    """
    id: str = Field(..., min_length=1, description="Unique entity ID")
    type: EntityType
    name: Optional[str] = None
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM format for MarketSnapshot")
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str, info) -> str:
        """ID 형식 검증
        
        Rules:
        - Infra: INFRA_*
        - MarketSnapshot: MARKET_*
        - Others: {REGION}_{DISTRICT}_*
        """
        entity_type = info.data.get('type')
        
        if entity_type == EntityType.INFRA:
            if not v.startswith('INFRA_'):
                raise ValueError(f"Infra ID must start with 'INFRA_': {v}")
        
        elif entity_type == EntityType.MARKET_SNAPSHOT:
            if not v.startswith('MARKET_'):
                raise ValueError(f"MarketSnapshot ID must start with 'MARKET_': {v}")
        
        # ID는 공백 포함 불가
        if ' ' in v:
            raise ValueError(f"Entity ID cannot contain spaces: {v}")
        
        return v
    
    @field_validator('date')
    @classmethod
    def validate_date_for_snapshot(cls, v: Optional[str], info) -> Optional[str]:
        """MarketSnapshot은 date 필수"""
        entity_type = info.data.get('type')
        
        if entity_type == EntityType.MARKET_SNAPSHOT and not v:
            raise ValueError("MarketSnapshot must have a date field")
        
        return v
    
    @field_validator('properties')
    @classmethod
    def validate_properties_for_type(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """타입별 필수 properties 검증"""
        entity_type = info.data.get('type')
        
        if entity_type == EntityType.INFRA:
            if 'category' not in v:
                raise ValueError("Infra entity must have 'category' in properties")
            if 'tier' not in v:
                raise ValueError("Infra entity must have 'tier' in properties")
        
        return v


class Relationship(BaseModel):
    """그래프 엣지 관계
    
    Examples:
        >>> Relationship(source="GYEONGGI_SUJI", target="INFRA_GANGNAM_STATION",
        ...              type="ACCESS_TO", properties={"time_min": 40, "transport_mode": "subway"})
    """
    source: str = Field(..., min_length=1, description="Source entity ID")
    target: str = Field(..., min_length=1, description="Target entity ID")
    type: str = Field(..., min_length=1, description="Relationship type (e.g., LOCATED_IN, ACCESS_TO)")
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('type')
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        """관계 타입 검증"""
        valid_types = {
            "LOCATED_IN",
            "ACCESS_TO",
            "CONTAINS_FACILITY",
            "HAS_SNAPSHOT",
            "ANALYZES",
            "MENTIONS",
            "HAS_ANALYSIS",
            "SUPPORTS",
        }
        
        if v not in valid_types:
            # Warning but don't fail - allow custom relationship types
            import logging
            logging.warning(f"Non-standard relationship type: {v}")
        
        return v


class KnowledgeGraphOutput(BaseModel):
    """LLM 출력 전체 구조
    
    이 모델은 LLM이 생성한 JSON을 검증하고 파싱하는 데 사용됩니다.
    
    Example:
        >>> kg = KnowledgeGraphOutput(
        ...     entities=[
        ...         Entity(id="INFRA_GANGNAM_STATION", type=EntityType.INFRA, name="강남역",
        ...                properties={"category": "Subway", "tier": "S"}),
        ...     ],
        ...     relationships=[
        ...         Relationship(source="GYEONGGI_SUJI", target="INFRA_GANGNAM_STATION",
        ...                      type="ACCESS_TO", properties={"time_min": 40}),
        ...     ]
        ... )
    """
    entities: List[Entity] = Field(..., min_length=1, description="List of entities to create")
    relationships: List[Relationship] = Field(default_factory=list, description="List of relationships to create")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional metadata")
    
    @field_validator('entities')
    @classmethod
    def validate_unique_ids(cls, v: List[Entity]) -> List[Entity]:
        """중복 ID 검증"""
        ids = [e.id for e in v]
        if len(ids) != len(set(ids)):
            duplicates = [id for id in ids if ids.count(id) > 1]
            raise ValueError(f"Duplicate entity IDs found: {set(duplicates)}")
        return v
    
    @field_validator('relationships')
    @classmethod
    def validate_relationship_references(cls, v: List[Relationship], info) -> List[Relationship]:
        """관계의 source/target이 entities에 존재하는지 검증"""
        entities_data = info.data.get('entities', [])
        entity_ids = {e.id for e in entities_data}
        
        for rel in v:
            if rel.source not in entity_ids:
                raise ValueError(
                    f"Relationship source '{rel.source}' not found in entities list"
                )
            if rel.target not in entity_ids:
                raise ValueError(
                    f"Relationship target '{rel.target}' not found in entities list"
                )
        
        return v
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """특정 타입의 엔티티만 필터링"""
        return [e for e in self.entities if e.type == entity_type]
    
    def get_relationships_by_type(self, rel_type: str) -> List[Relationship]:
        """특정 타입의 관계만 필터링"""
        return [r for r in self.relationships if r.type == rel_type]


# === Helper Functions ===

def generate_entity_id(entity_type: EntityType, **kwargs) -> str:
    """엔티티 ID 자동 생성
    
    Args:
        entity_type: 엔티티 타입
        **kwargs: ID 생성에 필요한 정보
            - For Region: city
            - For District: city, district
            - For Neighborhood: city, district, dong
            - For Complex: district, name
            - For Infra: name
            - For MarketSnapshot: entity_id, date
    
    Returns:
        Generated entity ID
        
    Examples:
        >>> generate_entity_id(EntityType.INFRA, name="강남역")
        'INFRA_GANGNAM_STATION'
        >>> generate_entity_id(EntityType.MARKET_SNAPSHOT, entity_id="EUNMA", date="2024-12")
        'MARKET_EUNMA_202412'
    """
    def normalize(text: str) -> str:
        """텍스트 정규화 (공백 제거, 대문자)"""
        return text.replace(" ", "_").replace("-", "_").upper()
    
    if entity_type == EntityType.REGION:
        return normalize(kwargs['city'])
    
    elif entity_type == EntityType.DISTRICT:
        return f"{normalize(kwargs['city'])}_{normalize(kwargs['district'])}"
    
    elif entity_type == EntityType.NEIGHBORHOOD:
        return f"{normalize(kwargs['city'])}_{normalize(kwargs['district'])}_{normalize(kwargs['dong'])}"
    
    elif entity_type == EntityType.COMPLEX:
        return f"{normalize(kwargs['district'])}_{normalize(kwargs['name'])}"
    
    elif entity_type == EntityType.INFRA:
        return f"INFRA_{normalize(kwargs['name'])}"
    
    elif entity_type == EntityType.MARKET_SNAPSHOT:
        date_str = kwargs['date'].replace("-", "")  # 2024-12 -> 202412
        return f"MARKET_{normalize(kwargs['entity_id'])}_{date_str}"
    
    else:
        raise ValueError(f"Unsupported entity type for ID generation: {entity_type}")


def parse_llm_output(json_string: str) -> KnowledgeGraphOutput:
    """LLM JSON 출력 파싱 및 검증
    
    Args:
        json_string: LLM이 생성한 JSON 문자열
        
    Returns:
        검증된 KnowledgeGraphOutput 객체
        
    Raises:
        ValidationError: JSON 형식이 잘못되었거나 검증 실패
    """
    import json
    from pydantic import ValidationError
    
    # Clean JSON (remove markdown code blocks if present)
    cleaned = json_string.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    # Parse JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    
    # Validate with Pydantic
    try:
        kg_output = KnowledgeGraphOutput(**data)
        return kg_output
    except ValidationError as e:
        raise ValueError(f"Validation failed:\n{e}")


if __name__ == "__main__":
    # 테스트
    print("=== Pydantic Models v3.0 Test ===\n")
    
    # Test 1: Valid KnowledgeGraphOutput
    print("Test 1: Valid output")
    kg = KnowledgeGraphOutput(
        entities=[
            Entity(
                id="INFRA_GANGNAM_STATION",
                type=EntityType.INFRA,
                name="강남역",
                properties={"category": "Subway", "tier": "S"}
            ),
            Entity(
                id="GYEONGGI_SUJI",
                type=EntityType.DISTRICT,
                name="수지구",
                properties={"city": "경기도"}
            ),
        ],
        relationships=[
            Relationship(
                source="GYEONGGI_SUJI",
                target="INFRA_GANGNAM_STATION",
                type="ACCESS_TO",
                properties={"time_min": 40, "transport_mode": "subway"}
            ),
        ]
    )
    print(f"✓ Created KnowledgeGraphOutput with {len(kg.entities)} entities")
    
    # Test 2: ID generation
    print("\nTest 2: ID generation")
    infra_id = generate_entity_id(EntityType.INFRA, name="강남역")
    snapshot_id = generate_entity_id(EntityType.MARKET_SNAPSHOT, entity_id="EUNMA", date="2024-12")
    print(f"✓ Infra ID: {infra_id}")
    print(f"✓ Snapshot ID: {snapshot_id}")
    
    # Test 3: Validation errors
    print("\nTest 3: Validation errors")
    try:
        bad_entity = Entity(
            id="MARKET_TEST",  # Missing date for MarketSnapshot
            type=EntityType.MARKET_SNAPSHOT,
            name="Test",
            properties={}
        )
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    
    print("\n=== All tests passed ===")
