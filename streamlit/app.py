"""
Real Estate GraphRAG Chat Interface

멀티모달 부동산 투자 분석 챗봇 UI

Features:
- 자연어 질의 → 그래프 검색 → AI 답변
- 검색 결과 그래프 시각화
- 투자 분석 근거 출처 표시
"""

import streamlit as st
import json
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


def init_session_state():
    """세션 상태 초기화"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "rag_engine" not in st.session_state:
        st.session_state.rag_engine = None
    if "connected" not in st.session_state:
        st.session_state.connected = False


def connect_services(falkordb_url: str, llm_url: str, model_name: str):
    """FalkorDB와 LLM 서비스 연결"""
    try:
        from falkordb import FalkorDB
        from openai import OpenAI
        from graphrag import HybridRAGEngine
        
        # FalkorDB 연결
        db = FalkorDB.from_url(falkordb_url)
        graph = db.select_graph("real_estate")
        
        # LLM 클라이언트
        llm_client = OpenAI(base_url=llm_url, api_key="EMPTY")
        
        # RAG 엔진 초기화
        st.session_state.rag_engine = HybridRAGEngine(
            graph=graph,
            llm_client=llm_client,
            model_name=model_name
        )
        st.session_state.connected = True
        
        return True, "연결 성공!"
    except Exception as e:
        return False, f"연결 실패: {e}"


def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.title("⚙️ 설정")
        
        # 연결 설정
        st.subheader("서비스 연결")
        
        falkordb_url = st.text_input(
            "FalkorDB URL",
            value="redis://localhost:6379",
            help="FalkorDB 연결 주소"
        )
        
        llm_url = st.text_input(
            "LLM API URL",
            value="http://localhost:8080/v1",
            help="llama.cpp 또는 vLLM 서버 주소"
        )
        
        model_name = st.text_input(
            "모델명",
            value="Qwen/Qwen3-VL-30B-A3B-Instruct",
            help="사용할 LLM 모델명"
        )
        
        if st.button("🔌 연결", use_container_width=True):
            with st.spinner("연결 중..."):
                success, message = connect_services(falkordb_url, llm_url, model_name)
                if success:
                    st.success(message)
                else:
                    st.error(message)
        
        # 연결 상태 표시
        if st.session_state.connected:
            st.success("✅ 연결됨")
            
            # 그래프 통계
            try:
                stats = st.session_state.rag_engine.get_graph_statistics()
                st.subheader("📊 그래프 통계")
                for label, count in stats.items():
                    st.metric(label, count)
            except Exception:
                pass
        else:
            st.warning("⚠️ 연결 필요")
        
        st.divider()
        
        # 예시 질문
        st.subheader("💡 예시 질문")
        examples = [
            "전세가율 60% 이상인 저평가 단지 찾아줘",
            "교통 S등급 지역의 아파트 단지들",
            "부산진구 공급물량 조회",
            "학군 A등급 이상 지역 분석",
        ]
        
        for example in examples:
            if st.button(example, use_container_width=True, type="secondary"):
                st.session_state.pending_question = example


def render_chat():
    """채팅 인터페이스 렌더링"""
    st.title("🏠 부동산 투자 분석 AI")
    st.caption("Wolbu 기준 기반 GraphRAG 시스템")
    
    # 채팅 히스토리 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # 추가 정보 표시 (AI 응답인 경우)
            if message["role"] == "assistant" and "metadata" in message:
                with st.expander("🔍 분석 상세"):
                    meta = message["metadata"]
                    
                    # Cypher 쿼리
                    if "cypher" in meta:
                        st.code(meta["cypher"], language="cypher")
                    
                    # 소스
                    if "sources" in meta and meta["sources"]:
                        st.write("**참조 데이터:**", ", ".join(meta["sources"]))
                    
                    # 신뢰도
                    if "confidence" in meta:
                        st.progress(meta["confidence"], text=f"신뢰도: {meta['confidence']:.0%}")
    
    # 예시 질문에서 온 경우
    if hasattr(st.session_state, 'pending_question'):
        user_input = st.session_state.pending_question
        del st.session_state.pending_question
        process_user_input(user_input)
    
    # 사용자 입력
    if user_input := st.chat_input("질문을 입력하세요...", disabled=not st.session_state.connected):
        process_user_input(user_input)


def process_user_input(user_input: str):
    """사용자 입력 처리"""
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # AI 응답 생성
    with st.chat_message("assistant"):
        with st.spinner("분석 중..."):
            try:
                result = st.session_state.rag_engine.query(user_input)
                
                st.markdown(result.answer)
                
                # 메타데이터 저장
                metadata = {
                    "cypher": result.cypher,
                    "sources": result.sources,
                    "confidence": result.confidence,
                    "graph_results": result.graph_results[:5],  # 상위 5개만
                }
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result.answer,
                    "metadata": metadata,
                })
                
                # 상세 정보 expander
                with st.expander("🔍 분석 상세"):
                    st.code(result.cypher, language="cypher")
                    if result.sources:
                        st.write("**참조 데이터:**", ", ".join(result.sources))
                    st.progress(result.confidence, text=f"신뢰도: {result.confidence:.0%}")
                
            except Exception as e:
                error_msg = f"오류가 발생했습니다: {e}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })


def main():
    """메인 함수"""
    st.set_page_config(
        page_title="부동산 투자 분석 AI",
        page_icon="🏠",
        layout="wide",
    )
    
    init_session_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
