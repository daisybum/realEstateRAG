#!/usr/bin/env python3
"""
Generate Evaluation Reports for Analysis Results

각 분석 결과를 입력 데이터와 비교하여 평가 리포트를 생성합니다.

Usage:
    # Quick summary (pandas table)
    python generate_evaluation_reports.py --quick --results_dir analysis_results
    
    # Full evaluation with individual reports
    python generate_evaluation_reports.py --results_dir analysis_results --data_dir ../realEstateCrawler/output
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import argparse

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


@dataclass
class EvaluationResult:
    """평가 결과 데이터"""
    report_id: str
    input_text: str
    input_text_length: int
    input_image_count: int
    
    # Extraction Quality
    region_detected: str
    region_accuracy: str  # ✅ / ⚠️ / ❌
    grades_extracted: Dict[str, str]
    complexes_count: int
    
    # Content Quality
    confidence_score: float
    has_repetition: bool
    has_warnings: bool
    warning_count: int
    reasoning_chain_present: bool
    
    # Overall
    overall_grade: str  # A / B / C / D / F
    strengths: list
    weaknesses: list


def load_analysis(filepath: Path) -> Optional[Dict]:
    """분석 결과 JSON 로드"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def load_input_data(data_dir: Path, report_id: str) -> tuple:
    """입력 데이터 (텍스트, 이미지 수) 로드"""
    report_dir = data_dir / report_id
    
    # 텍스트 파일 로드
    txt_file = report_dir / f"{report_id}.txt"
    text = ""
    if txt_file.exists():
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                text = f.read()
        except:
            pass
    
    # 이미지 수 카운트
    image_count = 0
    if report_dir.exists():
        image_count = len(list(report_dir.glob("*.jpg"))) + len(list(report_dir.glob("*.png")))
    
    return text, image_count


def parse_facts(facts_str: str) -> Dict:
    """facts 필드 파싱 (문자열 또는 딕셔너리)"""
    if isinstance(facts_str, dict):
        return facts_str
    
    try:
        # JSON 문자열인 경우
        clean = facts_str.strip()
        if clean.startswith('{'):
            return json.loads(clean)
    except:
        pass
    
    return {}


def evaluate_single(analysis: Dict, input_text: str = "", input_image_count: int = 0) -> EvaluationResult:
    """단일 분석 결과 평가"""
    report_id = analysis.get("report_id", "unknown")
    
    # Input Quality
    input_quality = analysis.get("input_quality", {})
    confidence = input_quality.get("confidence_score", 0.0)
    warnings = input_quality.get("hallucination_warnings", [])
    text_len = input_quality.get("text_length", len(input_text))
    img_count = input_quality.get("image_count", input_image_count)
    
    # Facts 파싱
    facts = parse_facts(analysis.get("facts", "{}"))
    
    # District 추출
    district = facts.get("district", {})
    region_name = district.get("name") or "Unknown"
    detected_region = district.get("detected_region", "Unknown")
    
    # 지역 정확도 판단 (제목에서 추출 가능한지 확인)
    region_accuracy = "⚠️"
    title_lower = input_text.lower() if input_text else ""
    if region_name and region_name != "Unknown":
        if title_lower and any(part in title_lower for part in region_name.split()[:2]):
            region_accuracy = "✅"
        else:
            region_accuracy = "⚠️ 추정"
    else:
        region_accuracy = "❌"
    
    # Grades 추출
    grades = district.get("grades", {})
    grades_extracted = {}
    for key in ["jobs", "transport", "school", "environment"]:
        grade_info = grades.get(key, {})
        if isinstance(grade_info, dict):
            grades_extracted[key] = grade_info.get("grade", "N/A")
        else:
            grades_extracted[key] = "N/A"
    
    # Complexes 카운트
    complexes = facts.get("complexes", [])
    district_complexes = district.get("complexes", [])
    total_complexes = len(complexes) + len(district_complexes)
    
    # Reasoning Chain 확인
    reasoning = facts.get("reasoning_chain", "") or district.get("reasoning_chain", "")
    has_reasoning = bool(reasoning and len(reasoning) > 50)
    
    # Insight 반복 확인
    insight = analysis.get("insight", "")
    has_repetition = (
        "반복 패턴 감지" in insight or 
        "repetitive content truncated" in insight.lower() or
        ("경고" in insight and "내용이 잘렸습니다" in insight)
    )
    
    # 강점/약점 분석
    strengths = []
    weaknesses = []
    
    if img_count > 50:
        strengths.append(f"대량 이미지({img_count}장) 처리 성공")
    if total_complexes > 5:
        strengths.append(f"다수 단지 추출({total_complexes}개)")
    if has_reasoning:
        strengths.append("명확한 추론 체인")
    if all(g != "N/A" for g in grades_extracted.values()):
        strengths.append("4개 등급 모두 평가 완료")
    if region_accuracy == "✅":
        strengths.append("지역 정확히 감지")
    
    if text_len < 100:
        weaknesses.append("입력 텍스트 부족 (제목만)")
    if has_repetition:
        weaknesses.append("반복 오류 발생")
    if len(warnings) > 0:
        weaknesses.append(f"경고 {len(warnings)}개")
    if confidence < 0.3:
        weaknesses.append(f"낮은 신뢰도 ({confidence:.2f})")
    if region_name == "Unknown" or region_name is None:
        weaknesses.append("지역 추출 실패")
    
    # Overall Grade 계산
    score = 0
    score += 2 if region_accuracy == "✅" else (1 if region_accuracy == "⚠️ 추정" else 0)
    score += 2 if total_complexes >= 5 else (1 if total_complexes > 0 else 0)
    score += 1 if has_reasoning else 0
    score += 1 if all(g != "N/A" for g in grades_extracted.values()) else 0
    score -= 1 if has_repetition else 0
    score -= 1 if len(warnings) > 1 else 0
    
    if score >= 5:
        overall_grade = "A"
    elif score >= 4:
        overall_grade = "B"
    elif score >= 2:
        overall_grade = "C"
    elif score >= 1:
        overall_grade = "D"
    else:
        overall_grade = "F"
    
    return EvaluationResult(
        report_id=report_id,
        input_text=input_text[:200] + "..." if len(input_text) > 200 else input_text,
        input_text_length=text_len,
        input_image_count=img_count,
        region_detected=f"{region_name} ({detected_region})",
        region_accuracy=region_accuracy,
        grades_extracted=grades_extracted,
        complexes_count=total_complexes,
        confidence_score=confidence,
        has_repetition=has_repetition,
        has_warnings=len(warnings) > 0,
        warning_count=len(warnings),
        reasoning_chain_present=has_reasoning,
        overall_grade=overall_grade,
        strengths=strengths,
        weaknesses=weaknesses,
    )


def generate_report_markdown(result: EvaluationResult, analysis: Dict) -> str:
    """마크다운 형식의 평가 리포트 생성"""
    
    # Insight 미리보기 (첫 500자)
    insight = analysis.get("insight", "")
    insight_preview = insight[:500] + "..." if len(insight) > 500 else insight
    
    md = f"""# 📊 평가 리포트: Report {result.report_id}

## 📋 기본 정보

| 항목 | 값 |
|:---|:---|
| **Report ID** | {result.report_id} |
| **Overall Grade** | **{result.overall_grade}** |
| **신뢰도 점수** | {result.confidence_score:.2f} |
| **입력 텍스트 길이** | {result.input_text_length}자 |
| **입력 이미지 수** | {result.input_image_count}장 |

---

## 📝 입력 데이터

```
{result.input_text}
```

---

## 🎯 추출 결과 평가

### 지역 감지
| 항목 | 결과 |
|:---|:---|
| **감지된 지역** | {result.region_detected} |
| **정확도** | {result.region_accuracy} |

### 입지 등급 (Location Grades)
| 항목 | 등급 |
|:---|:---:|
| **직장 (Jobs)** | {result.grades_extracted.get('jobs', 'N/A')} |
| **교통 (Transport)** | {result.grades_extracted.get('transport', 'N/A')} |
| **학군 (School)** | {result.grades_extracted.get('school', 'N/A')} |
| **환경 (Environment)** | {result.grades_extracted.get('environment', 'N/A')} |

### 단지 분석
- **추출된 단지 수**: {result.complexes_count}개

---

## ✅ 강점

"""
    for s in result.strengths:
        md += f"- {s}\n"
    
    if not result.strengths:
        md += "- (없음)\n"
    
    md += """
## ⚠️ 개선 필요 사항

"""
    for w in result.weaknesses:
        md += f"- {w}\n"
    
    if not result.weaknesses:
        md += "- (없음)\n"
    
    md += f"""
---

## 📈 품질 지표

| 지표 | 상태 |
|:---|:---:|
| **추론 체인** | {"✅ 있음" if result.reasoning_chain_present else "❌ 없음"} |
| **반복 오류** | {"❌ 발생" if result.has_repetition else "✅ 없음"} |
| **경고** | {"⚠️ 있음" if result.has_warnings else "✅ 없음"} |

---

## 💡 Insight 미리보기

{insight_preview}

---

*Generated by LLM Evaluation System*
"""
    return md


def quick_evaluate(results_dir: str = "analysis_results") -> List[EvaluationResult]:
    """빠른 평가 (pandas 테이블 출력, evaluate_results.py 기능)"""
    results_path = Path(results_dir)
    files = sorted(results_path.glob("*_analysis.json"))
    
    print(f"Found {len(files)} analysis results in {results_path}.")
    
    all_results = []
    
    for f in files:
        try:
            analysis = load_analysis(f)
            if not analysis:
                continue
            
            result = evaluate_single(analysis)
            all_results.append(result)
            
        except Exception as e:
            print(f"Error parsing {f}: {e}")
    
    if not all_results:
        print("No data to evaluate.")
        return []
    
    # Pandas 테이블 생성
    if PANDAS_AVAILABLE:
        data = []
        for r in all_results:
            data.append({
                "Report ID": r.report_id,
                "Grade": r.overall_grade,
                "Confidence": r.confidence_score,
                "Text Len": r.input_text_length,
                "Images": r.input_image_count,
                "Region": r.region_detected[:25] + "..." if len(r.region_detected) > 25 else r.region_detected,
                "Complexes": r.complexes_count,
                "Repetition": r.has_repetition,
                "Warnings": r.warning_count
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values("Confidence", ascending=False)
        
        print("\n=== Evaluation Summary ===")
        print(df.to_markdown(index=False))
        
        print("\n=== Quality Statistics ===")
        print(f"Average Confidence: {df['Confidence'].mean():.2f}")
        print(f"Repetition Errors: {df['Repetition'].sum()}")
        print(f"Reports with Warnings: {(df['Warnings'] > 0).sum()}")
        
        # Grade 분포
        print("\n=== Grade Distribution ===")
        for grade in ["A", "B", "C", "D", "F"]:
            count = len([r for r in all_results if r.overall_grade == grade])
            pct = count / len(all_results) * 100
            print(f"  {grade}: {count} ({pct:.1f}%)")
    else:
        print("\n[Warning] pandas not available, showing basic stats only")
        print(f"Total: {len(all_results)}")
        for grade in ["A", "B", "C", "D", "F"]:
            count = len([r for r in all_results if r.overall_grade == grade])
            print(f"  {grade}: {count}")
    
    return all_results


def full_evaluate(results_dir: str, data_dir: str, output_dir: str = None):
    """전체 평가 (개별 리포트 + 요약)"""
    results_path = Path(results_dir)
    data_path = Path(data_dir)
    out_path = Path(output_dir) if output_dir else results_path
    
    # 결과 파일 목록
    result_files = sorted(results_path.glob("*_analysis.json"))
    print(f"Found {len(result_files)} analysis results in {results_path}")
    
    # 통계
    grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    all_results = []
    
    for filepath in result_files:
        report_id = filepath.stem.replace("_analysis", "")
        
        # 분석 결과 로드
        analysis = load_analysis(filepath)
        if not analysis:
            continue
        
        # 입력 데이터 로드
        input_text, image_count = load_input_data(data_path, report_id)
        
        # 평가
        result = evaluate_single(analysis, input_text, image_count)
        all_results.append(result)
        grades[result.overall_grade] += 1
        
        # 리포트 생성
        report_md = generate_report_markdown(result, analysis)
        
        # 저장
        output_file = out_path / f"{report_id}_evaluation.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_md)
        
        print(f"  [{result.overall_grade}] {report_id}: {result.region_detected}")
    
    # 종합 통계
    print(f"\n=== 종합 통계 ===")
    print(f"Total: {len(all_results)}")
    for grade, count in sorted(grades.items()):
        pct = count / len(all_results) * 100 if all_results else 0
        print(f"  {grade}: {count} ({pct:.1f}%)")
    
    # 종합 리포트
    summary_md = f"""# 📊 전체 평가 요약 리포트

## 📋 통계

| 등급 | 개수 | 비율 |
|:---:|:---:|:---:|
"""
    for grade in ["A", "B", "C", "D", "F"]:
        count = grades[grade]
        pct = count / len(all_results) * 100 if all_results else 0
        summary_md += f"| **{grade}** | {count} | {pct:.1f}% |\n"
    
    summary_md += f"""
## 📈 상세 결과

| Report ID | Grade | Region | Complexes | Confidence |
|:---|:---:|:---|:---:|:---:|
"""
    for r in sorted(all_results, key=lambda x: x.overall_grade):
        region_short = r.region_detected[:30] + "..." if len(r.region_detected) > 30 else r.region_detected
        summary_md += f"| {r.report_id} | {r.overall_grade} | {region_short} | {r.complexes_count} | {r.confidence_score:.2f} |\n"
    
    summary_file = out_path / "EVALUATION_SUMMARY.md"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary_md)
    
    print(f"\n✅ Summary saved to {summary_file}")
    
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate analysis results and generate reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick summary (pandas table only)
  python generate_evaluation_reports.py --quick --results_dir temp
  
  # Full evaluation with individual markdown reports
  python generate_evaluation_reports.py --results_dir temp --data_dir ../realEstateCrawler/output
  
  # Alias for quick mode (backwards compatibility with evaluate_results.py)
  python generate_evaluation_reports.py --output_dir analysis_results
        """
    )
    parser.add_argument("--quick", action="store_true", help="Quick mode: pandas summary only, no individual reports")
    parser.add_argument("--results_dir", type=str, default=None, help="Directory containing analysis results (for full mode)")
    parser.add_argument("--output_dir", type=str, default=None, help="Alias for --results_dir (backwards compatibility)")
    parser.add_argument("--data_dir", type=str, default="../realEstateCrawler/output", help="Directory containing input data")
    args = parser.parse_args()
    
    # Backwards compatibility: --output_dir as alias for --results_dir in quick mode
    results_dir = args.results_dir or args.output_dir or "analysis_results"
    
    if args.quick or (args.output_dir and not args.results_dir):
        # Quick mode (original evaluate_results.py behavior)
        quick_evaluate(results_dir)
    else:
        # Full mode with individual reports
        full_evaluate(results_dir, args.data_dir)


if __name__ == "__main__":
    main()

