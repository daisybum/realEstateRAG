"""
Qwen VL Analyzer

vLLM 서버 기반 Qwen Vision-Language 모델 분석기
청크 기반 대용량 이미지 처리 지원
"""
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from openai import OpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class QwenAnalyzer:
    """vLLM 기반 Qwen VL 분석기
    
    OpenAI 호환 API를 사용하여 멀티모달 분석 수행
    대용량 이미지는 청크 단위로 분할 처리 후 결과 병합
    
    Example:
        >>> analyzer = QwenAnalyzer(model_name="Qwen/Qwen3-VL-30B-A3B-Instruct")
        >>> result = analyzer.analyze(text, images, prompt)
    """
    
    DEFAULT_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    DEFAULT_TEMPERATURE = 0.1
    DEFAULT_MAX_TOKENS = 8192
    MAX_IMAGES_PER_CHUNK = 8  # 더 작은 청크로 토큰 오버플로우 방지
    
    def __init__(self, 
                 api_key: str = "EMPTY", 
                 base_url: str = "http://localhost:8000/v1",
                 model_name: Optional[str] = None,
                 temperature: float = DEFAULT_TEMPERATURE,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 max_images_per_chunk: int = MAX_IMAGES_PER_CHUNK):
        """
        Args:
            api_key: vLLM 서버 API 키 (기본: EMPTY)
            base_url: vLLM 서버 URL
            model_name: 모델명 (None이면 환경변수 또는 기본값 사용)
            temperature: 생성 온도 (낮을수록 결정적)
            max_tokens: 최대 출력 토큰
            max_images_per_chunk: 청크당 최대 이미지 개수
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name or self._get_model_name()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_images_per_chunk = max_images_per_chunk
        
        logger.info(f"Initialized QwenAnalyzer with model: {self.model_name}")
    
    def _get_model_name(self) -> str:
        """환경변수 또는 기본값에서 모델명 가져오기"""
        import os
        return os.environ.get("MODEL_NAME", self.DEFAULT_MODEL)
    
    def analyze(self, 
                text: str, 
                images: List[str], 
                prompt_template: ChatPromptTemplate, 
                **kwargs) -> str:
        """멀티모달 분석 수행 (청크 처리 포함)
        
        Args:
            text: 보고서 텍스트
            images: 이미지 경로 리스트
            prompt_template: LangChain ChatPromptTemplate
            **kwargs: 프롬프트 템플릿 변수들
            
        Returns:
            분석 결과 문자열 (청크 결과 병합)
        """
        # 이미지가 청크 제한 이하면 단일 처리
        if len(images) <= self.max_images_per_chunk:
            return self._analyze_single(text, images, prompt_template, **kwargs)
        
        # 청크 분할 처리
        logger.info(f"Chunked processing: {len(images)} images in {self._calculate_chunks(len(images))} chunks")
        return self._analyze_chunked(text, images, prompt_template, **kwargs)
    
    def _calculate_chunks(self, total_images: int) -> int:
        """필요한 청크 수 계산"""
        return (total_images + self.max_images_per_chunk - 1) // self.max_images_per_chunk
    
    def _analyze_single(self,
                        text: str,
                        images: List[str],
                        prompt_template: ChatPromptTemplate,
                        **kwargs) -> str:
        """단일 청크 분석"""
        messages = self._build_messages(text, images, prompt_template, **kwargs)
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return f"Error during analysis: {e}"
    
    def _analyze_chunked(self,
                         text: str,
                         images: List[str],
                         prompt_template: ChatPromptTemplate,
                         **kwargs) -> str:
        """청크 분할 분석 + 결과 병합
        
        Phase 1: 각 청크 개별 분석
        Phase 2: 결과 병합 (JSON 병합 또는 텍스트 연결)
        """
        # 이미지 청크 분할
        chunks = self._split_into_chunks(images)
        total_chunks = len(chunks)
        chunk_results = []
        
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"  Processing chunk {i}/{total_chunks} ({len(chunk)} images)...")
            
            # 청크 컨텍스트 추가
            chunk_context = f"\n[Analyzing chunk {i}/{total_chunks}, images {(i-1)*self.max_images_per_chunk + 1}-{(i-1)*self.max_images_per_chunk + len(chunk)}]\n"
            chunk_text = text + chunk_context
            
            result = self._analyze_single(chunk_text, chunk, prompt_template, **kwargs)
            chunk_results.append({
                "chunk_id": i,
                "image_count": len(chunk),
                "result": result
            })
        
        # 결과 병합
        return self._merge_chunk_results(chunk_results)
    
    def _split_into_chunks(self, images: List[str]) -> List[List[str]]:
        """이미지 리스트를 청크로 분할"""
        chunks = []
        for i in range(0, len(images), self.max_images_per_chunk):
            chunks.append(images[i:i + self.max_images_per_chunk])
        return chunks
    
    def _merge_chunk_results(self, chunk_results: List[Dict]) -> str:
        """청크 결과 병합
        
        JSON 결과: 필드별 병합
        텍스트 결과: 연결
        """
        if not chunk_results:
            return "{}"
        
        # 단일 청크면 그대로 반환
        if len(chunk_results) == 1:
            return chunk_results[0]["result"]
        
        # JSON 병합 시도
        merged_json = self._try_merge_json_results(chunk_results)
        if merged_json:
            return merged_json
        
        # JSON 파싱 실패 시 텍스트 연결
        return self._merge_text_results(chunk_results)
    
    def _try_merge_json_results(self, chunk_results: List[Dict]) -> Optional[str]:
        """JSON 결과 병합 시도 (필드 정제 + JSON 수리 포함)"""
        try:
            parsed_results = []
            for cr in chunk_results:
                result_str = cr["result"]
                # JSON 블록 추출
                clean = result_str.replace("```json", "").replace("```", "").strip()
                
                # JSON 시작/끝 찾기 (잘못된 내용 제거)
                start_idx = clean.find("{")
                end_idx = clean.rfind("}")
                if start_idx == -1 or end_idx == -1:
                    logger.warning(f"Chunk {cr['chunk_id']}: No valid JSON found")
                    continue
                
                clean = clean[start_idx:end_idx + 1]
                
                # JSON 수리 시도
                clean = self._repair_json(clean)
                
                try:
                    parsed = json.loads(clean)
                except json.JSONDecodeError as e:
                    logger.warning(f"Chunk {cr['chunk_id']}: JSON parse error after repair: {e}")
                    continue
                
                # 필드 정제 (긴 문자열 잘라내기)
                parsed = self._sanitize_json_fields(parsed)
                parsed_results.append(parsed)
            
            if not parsed_results:
                return None
            
            # 결과 병합
            merged = self._deep_merge_dicts(parsed_results)
            merged["_chunk_info"] = {
                "total_chunks": len(chunk_results),
                "merged": True,
                "parsed_chunks": len(parsed_results)
            }
            
            # 최종 결과 크기 제한 (20KB)
            result_json = json.dumps(merged, ensure_ascii=False, indent=2)
            if len(result_json) > 20000:
                logger.warning(f"Merged JSON too large ({len(result_json)} chars), summarizing...")
                merged = self._summarize_merged_result(merged)
                result_json = json.dumps(merged, ensure_ascii=False, indent=2)
            
            return result_json
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"JSON merge failed: {e}")
            return None
    
    def _repair_json(self, json_str: str) -> str:
        """일반적인 JSON 구문 오류 수리"""
        import re
        
        # 1. 후행 쉼표 제거 (배열과 객체 끝)
        json_str = re.sub(r',(\s*[\]}])', r'\1', json_str)
        
        # 2. 누락된 쉼표 추가 (}{ 또는 ][ 사이)
        json_str = re.sub(r'(\})\s*(\{)', r'\1,\2', json_str)
        json_str = re.sub(r'(\])\s*(\[)', r'\1,\2', json_str)
        
        # 3. 잘린 문자열 내 이스케이프 안 된 따옴표 처리
        # 이 부분은 복잡하므로 간단한 케이스만 처리
        
        # 4. 불완전한 JSON 끝 처리 (열린 괄호 닫기)
        open_braces = json_str.count('{') - json_str.count('}')
        open_brackets = json_str.count('[') - json_str.count(']')
        
        if open_braces > 0:
            json_str = json_str.rstrip() + '}' * open_braces
        if open_brackets > 0:
            json_str = json_str.rstrip() + ']' * open_brackets
        
        # 5. 불완전한 문자열 닫기 (홀수 따옴표)
        # 마지막 키-값 쌍이 불완전하면 제거
        if json_str.count('"') % 2 != 0:
            # 마지막 불완전한 문자열 찾아 제거
            last_quote = json_str.rfind('"')
            if last_quote > 0:
                # 마지막 쉼표까지 잘라내기
                last_comma = json_str.rfind(',', 0, last_quote)
                if last_comma > 0:
                    json_str = json_str[:last_comma] + json_str[last_quote+1:].lstrip()
        
        return json_str
    
    def _sanitize_json_fields(self, data: Dict, max_str_len: int = 1000) -> Dict:
        """JSON 필드 정제 - 긴 문자열 잘라내기, 반복 패턴 제거"""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                # 긴 문자열 잘라내기
                if len(value) > max_str_len:
                    # 반복 패턴 감지 (같은 문장 3번 이상 반복)
                    if self._has_repetition(value):
                        value = value[:500] + "... [repetitive content truncated]"
                    else:
                        value = value[:max_str_len] + "... [truncated]"
                result[key] = value
            elif isinstance(value, dict):
                result[key] = self._sanitize_json_fields(value, max_str_len)
            elif isinstance(value, list):
                result[key] = [
                    self._sanitize_json_fields(item, max_str_len) if isinstance(item, dict)
                    else (item[:max_str_len] + "..." if isinstance(item, str) and len(item) > max_str_len else item)
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def _has_repetition(self, text: str, min_chunk: int = 50) -> bool:
        """텍스트에 반복 패턴이 있는지 감지"""
        if len(text) < min_chunk * 3:
            return False
        
        # 50자 단위로 비교
        chunks = [text[i:i+min_chunk] for i in range(0, len(text) - min_chunk, min_chunk)]
        if len(chunks) < 3:
            return False
        
        # 첫 번째 청크가 3번 이상 나타나면 반복으로 판단
        first_chunk = chunks[0]
        count = sum(1 for c in chunks if c == first_chunk)
        return count >= 3
    
    def _summarize_merged_result(self, data: Dict) -> Dict:
        """병합된 결과 요약 (크기 제한용)"""
        result = {}
        
        # 핵심 필드만 유지
        priority_keys = ["district", "entity_type", "name", "grades", "properties", 
                        "investment_comment", "complexes", "_chunk_info"]
        
        for key in priority_keys:
            if key in data:
                value = data[key]
                # complexes 리스트는 최대 10개로 제한
                if key == "complexes" and isinstance(value, list) and len(value) > 10:
                    result[key] = value[:10]
                    result["_complexes_truncated"] = f"Showing 10 of {len(value)}"
                else:
                    result[key] = value
        
        return result
    
    def _deep_merge_dicts(self, dicts: List[Dict]) -> Dict:
        """딕셔너리 리스트 깊은 병합
        
        - 리스트: 중복 제거 후 연결
        - 딕셔너리: 재귀 병합
        - 스칼라: 마지막 값 우선 (null이 아닌 값 우선)
        """
        if not dicts:
            return {}
        
        result = {}
        all_keys = set()
        for d in dicts:
            if isinstance(d, dict):
                all_keys.update(d.keys())
        
        for key in all_keys:
            values = [d.get(key) for d in dicts if isinstance(d, dict) and key in d]
            values = [v for v in values if v is not None]
            
            if not values:
                result[key] = None
            elif all(isinstance(v, dict) for v in values):
                # 딕셔너리 재귀 병합
                result[key] = self._deep_merge_dicts(values)
            elif all(isinstance(v, list) for v in values):
                # 리스트 병합 (중복 제거)
                merged_list = []
                seen = set()
                for lst in values:
                    for item in lst:
                        item_key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            merged_list.append(item)
                result[key] = merged_list
            else:
                # 스칼라: 충돌 감지 후 최빈값 선택
                result[key] = self._resolve_scalar_conflict(key, values)
        
        return result
    
    def _resolve_scalar_conflict(self, key: str, values: List) -> Any:
        """스칼라 값 충돌 해결 - 비현실적 값 필터링 + 최빈값 선택"""
        if len(values) == 1:
            return values[0]
        
        # 비현실적 값 필터링 (구/군 단위 기준)
        # 한국의 구/군 인구는 대부분 50만 이하
        REASONABLE_LIMITS = {
            'population': 1_000_000,       # 인구 100만 이하
            'worker_count': 500_000,       # 종사자 50만 이하
            'supply_volume_3yr': 100_000,  # 3년 공급량 10만 이하
            'appropriate_demand': 50_000,  # 적정수요 5만 이하
        }
        
        if key in REASONABLE_LIMITS:
            limit = REASONABLE_LIMITS[key]
            filtered = [v for v in values if isinstance(v, (int, float)) and v <= limit]
            if filtered:
                values = filtered
                logger.debug(f"Filtered unrealistic values for '{key}': kept {len(filtered)} values")
        
        # 숫자 필드 충돌 감지
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        if len(numeric_values) > 1:
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            
            # 50% 이상 차이면 경고
            if min_val > 0 and (max_val - min_val) / min_val > 0.5:
                logger.warning(f"Data conflict in '{key}': values differ >50% ({values})")
        
        # 최빈값 선택 (Counter 사용)
        from collections import Counter
        
        # 해시 가능한 값만 사용
        hashable_values = []
        for v in values:
            try:
                hash(v)
                hashable_values.append(v)
            except TypeError:
                hashable_values.append(str(v))
        
        if hashable_values:
            counter = Counter(hashable_values)
            most_common = counter.most_common(1)[0][0]
            return most_common
        
        # 기본: 마지막 값
        return values[-1]
    
    def _merge_text_results(self, chunk_results: List[Dict]) -> str:
        """텍스트 결과 연결"""
        parts = []
        for cr in chunk_results:
            parts.append(f"=== Chunk {cr['chunk_id']} ({cr['image_count']} images) ===\n{cr['result']}")
        return "\n\n".join(parts)
    
    def _build_messages(self,
                        text: str,
                        images: List[str],
                        prompt_template: ChatPromptTemplate,
                        **kwargs) -> List[Dict[str, Any]]:
        """OpenAI 호환 메시지 구성"""
        # LangChain 템플릿 포맷팅
        formatted = prompt_template.format_messages(report_text=text, **kwargs)
        
        system_content = formatted[0].content
        user_content_text = formatted[1].content if len(formatted) > 1 else ""
        
        # 메시지 구성
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": self._build_user_content(user_content_text, images),
            },
        ]
        
        return messages
    
    def _build_user_content(self, 
                            text: str, 
                            images: List[str]) -> List[Dict[str, Any]]:
        """사용자 메시지 콘텐츠 구성 (텍스트 + 이미지)"""
        content = [{"type": "text", "text": text}]
        
        for img_path in images:
            # 로컬 파일인 경우 base64로 인코딩하여 전송 (컨테이너/호스트 경로 문제 해결)
            try:
                base64_image = self._encode_image(img_path)
                image_url = f"data:image/jpeg;base64,{base64_image}"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })
            except Exception as e:
                logger.warning(f"Failed to load image {img_path}: {e}")
        
        return content

    def _encode_image(self, image_path: str) -> str:
        """이미지 파일을 base64 문자열로 인코딩"""
        import base64
        
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')


if __name__ == "__main__":
    # 테스트
    analyzer = QwenAnalyzer()
    print(f"Initialized analyzer for model: {analyzer.model_name}")
    print(f"Max images per chunk: {analyzer.max_images_per_chunk}")
