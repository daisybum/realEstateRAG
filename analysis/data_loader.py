"""
Data Loader Module

파일 시스템에서 부동산 보고서 데이터를 로드하는 모듈
"""
import logging
from typing import List, Dict, Optional, Union
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReportData:
    """보고서 데이터 컨테이너"""
    id: str
    text: str
    images: List[str]
    pdf: Optional[str] = None
    pptx: Optional[str] = None
    
    @property
    def is_empty(self) -> bool:
        """보고서가 비어있는지 확인"""
        return not self.text and not self.images


class DataLoader:
    """파일 시스템 기반 데이터 로더
    
    보고서 폴더 구조:
        base_path/
        ├── {report_id}/
        │   ├── {report_id}.txt
        │   ├── image_1.png
        │   ├── image_2.png
        │   └── report.pdf (optional)
    """
    
    def __init__(self, base_path: Union[str, Path]):
        """
        Args:
            base_path: 보고서 폴더들이 위치한 기본 디렉토리
        """
        self.base_path = Path(base_path).expanduser()
        
        if not self.base_path.exists():
            logger.warning(f"Base path does not exist: {self.base_path}")
    
    def get_report_ids(self) -> List[str]:
        """모든 보고서 ID 목록 반환 (최신순 정렬)
        
        Returns:
            숫자로 된 폴더명 리스트 (내림차순)
        
        Raises:
            FileNotFoundError: 기본 경로가 존재하지 않는 경우
        """
        if not self.base_path.exists():
            raise FileNotFoundError(f"Base path {self.base_path} does not exist.")
        
        report_ids = [
            d.name for d in self.base_path.iterdir() 
            if d.is_dir() and d.name.isdigit()
        ]
        return sorted(report_ids, key=lambda x: int(x), reverse=True)
    
    def load_report(self, report_id: str) -> ReportData:
        """특정 보고서 로드
        
        Args:
            report_id: 보고서 ID (폴더명)
            
        Returns:
            ReportData 객체
            
        Raises:
            FileNotFoundError: 보고서 폴더가 존재하지 않는 경우
        """
        report_dir = self.base_path / report_id
        if not report_dir.exists():
            raise FileNotFoundError(f"Report directory {report_dir} does not exist.")
        
        # 텍스트 로드
        text = self._load_text(report_dir, report_id)
        
        # 이미지 로드 (정렬됨)
        images = self._load_images(report_dir)
        
        # PDF/PPTX 경로 확인
        pdf = self._find_file(report_dir, "*.pdf")
        pptx = self._find_file(report_dir, "*.pptx")
        
        return ReportData(
            id=report_id,
            text=text,
            images=images,
            pdf=pdf,
            pptx=pptx,
        )
    
    def _load_text(self, report_dir: Path, report_id: str) -> str:
        """텍스트 파일 로드"""
        txt_file = report_dir / f"{report_id}.txt"
        if not txt_file.exists():
            return ""
        
        try:
            return txt_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading text file {txt_file}: {e}")
            return ""
    
    def _load_images(self, report_dir: Path) -> List[str]:
        """이미지 파일 경로들 로드 (정렬됨) - png, jpg, jpeg 지원"""
        images = []
        for ext in ["*.png", "*.jpg", "*.jpeg"]:
            images.extend(report_dir.glob(ext))
        images = sorted(images, key=lambda x: x.name)
        return [str(img.absolute()) for img in images]
    
    def _find_file(self, report_dir: Path, pattern: str) -> Optional[str]:
        """특정 패턴의 파일 찾기"""
        files = list(report_dir.glob(pattern))
        return str(files[0].absolute()) if files else None


if __name__ == "__main__":
    # 테스트
    import sys
    
    loader = DataLoader("~/Projects/realEstateCrawler/output/")
    
    try:
        report_ids = loader.get_report_ids()
        print(f"Found {len(report_ids)} reports.")
        
        if report_ids:
            data = loader.load_report(report_ids[0])
            print(f"Loaded report {data.id}:")
            print(f"  - Text length: {len(data.text)}")
            print(f"  - Image count: {len(data.images)}")
            print(f"  - Is empty: {data.is_empty}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
