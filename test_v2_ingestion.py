#!/usr/bin/env python3
"""
Schema v2.0 검증 - 모의 데이터 테스트

실제 분석 결과와 유사한 모의 JSON으로 v2.0 스키마 검증
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from falkordb import FalkorDB
from graphrag import GraphIngesterV2
from graphrag.graph_schema import GraphSchemaManager

# 모의 분석 결과 (사용자가 제공한 예시 기반)
MOCK_RESULT = {
    "report_id": "3667403",
    "input_quality": {
        "confidence_score": 0.85,
        "text_length": 2500,
        "image_count": 15,
        "data_sources": ["full_text", "images_15"],
        "hallucination_warnings": []
    },
    "facts": {
        "district": {
            "name": "부산진구",
            "population": 44035,
            "appropriate_demand": 220
        },
        "grades": {
            "jobs": {"grade": "A", "raw_value": 176113, "evidence": "서면 상권 인접, 기업 밀집 지역"},
            "transport": {"grade": "S", "evidence": "서면역 도보 10분, 1호선 접근성 우수"},
            "school": {"grade": "B", "raw_value": 7.2, "evidence": "중위권 학군"},
            "environment": {"grade": "A", "evidence": "백화점 500m, 대형마트 800m"}
        },
        "complexes": [
            {
                "name": "가야롯데캐슬골드아너",
                "sales_price": 62000,
                "jeonse_price": 40000,
                "gap_price": 22000,
                "jeonse_rate": 64.52,
                "is_undervalued": True,
                "investment_comment": "전고점 대비 하락폭 0.93%, 소득 대비 저평가 구간 확인. 교통 S등급으로 향후 상승 가능성 높음."
            },
            {
                "name": "부산진구청역롯데캐슬",
                "sales_price": 58000,
                "jeonse_price": 35000,
                "gap_price": 23000,
                "jeonse_rate": 60.34,
                "is_undervalued": True,
                "investment_comment": "학군 B등급이나 교통 S등급으로 보완. 갭투자 적정."
            }
        ],
        "supply": {
            "yearly_volume": {
                "2024": 1500,
                "2025": 2000,
                "2026": 656
            },
            "risk_status": "Medium"
        }
    },
    "verification": "이미지 검증 완료",
    "sentiment": {
        "sentiment_score": {"value": 0.7, "interpretation": "긍정적"},
        "investment_timing": "적극 매수"
    },
    "insight": "부산진구는 교통 S등급과 직장 A등급으로 입지 우수. 저평가 단지 2개 확인."
}


def main():
    print("="*60)
    print("Schema v2.0 검증 테스트 (모의 데이터)")
    print("="*60)
    
    # 1. FalkorDB 연결
    print("\n1️⃣  FalkorDB 연결...")
    db = FalkorDB.from_url("redis://localhost:6379")
    graph = db.select_graph("real_estate")
    print("   ✅ Connected")
    
    # 2. 기존 데이터 삭제 (테스트용)
    print("\n2️⃣  데이터 초기화...")
    manager = GraphSchemaManager(graph)
    manager.drop_all()
    print("   ✅ Cleared")
    
    # 3. 스키마 초기화
    print("\n3️⃣  Schema v2.0 초기화...")
    manager.initialize_schema()
    print("   ✅ Schema ready")
    
    # 4. 모의 데이터 적재
    print("\n4️⃣  모의 데이터 적재...")
    ingester = GraphIngesterV2(graph, auto_init_schema=False)
    stats = ingester.ingest_analysis_result(MOCK_RESULT)
    
    print(f"\n   📊 적재 통계:")
    print(f"      • 생성된 노드: {stats['nodes_created']}")
    print(f"      • 생성된 관계: {stats['relationships_created']}")
    print(f"      • Report: {stats['reports']}")
    print(f"      • Complex: {stats['complexes']}")
    print(f"      • Analysis: {stats['analyses']}")
    print(f"      • Indicator: {stats['indicators']}")
    
    # 5. 그래프 통계 확인
    print("\n5️⃣  그래프 통계 확인...")
    graph_stats = manager.get_statistics()
    
    print(f"\n   📈 노드 개수:")
    for label, count in graph_stats.items():
        if count > 0:
            print(f"      • {label}: {count}")
    
    # 6. 추론 체인 조회 테스트
    print("\n6️⃣  추론 체인 조회 테스트...")
    query = """
    MATCH (c:ApartmentComplex {name: '가야롯데캐슬골드아너'})
          -[:HAS_ANALYSIS]->(a:InvestmentAnalysis)
    OPTIONAL MATCH (a)<-[:SUPPORTS]-(g:GradeMetric)
    RETURN a.verdict as verdict, 
           a.reasoning as reasoning,
           a.confidence as confidence,
           collect({category: g.category, grade: g.grade}) as supporting_grades
    """
    
    result = graph.query(query)
    if result.result_set:
        row = result.result_set[0]
        print(f"\n   🔍 추론 체인 결과:")
        print(f"      • 판단: {row[0]}")
        print(f"      • 근거: {row[1]}")
        print(f"      • 신뢰도: {row[2]}")
        print(f"      • 뒷받침 등급: {row[3]}")
    else:
        print("   ⚠️  추론 체인 데이터 없음")
    
    # 7. 지표 기반 리스크 분석
    print("\n7️⃣  공급 리스크 분석...")
    risk_query = """
    MATCH (r:Region)-[:HAS_INDICATOR]->(i1:Indicator {type: 'supply_volume_3yr'})
    MATCH (r)-[:HAS_INDICATOR]->(i2:Indicator {type: 'appropriate_demand'})
    RETURN r.name as region,
           i1.value as supply,
           i2.value as demand,
           toFloat(i1.value) / toFloat(i2.value) as risk_ratio
    """
    
    result = graph.query(risk_query)
    if result.result_set:
        row = result.result_set[0]
        print(f"\n   ⚠️  공급 리스크:")
        print(f"      • 지역: {row[0]}")
        print(f"      • 3년 공급: {row[1]} 세대")
        print(f"      • 적정 수요: {row[2]} 세대")
        print(f"      • 리스크 비율: {row[3]:.2f}x")
    else:
        print("   ⚠️  공급 데이터 없음")
    
    print("\n"+"="*60)
    print("✅ Schema v2.0 검증 완료!")
    print("="*60)
    
    return stats, graph_stats


if __name__ == "__main__":
    main()
