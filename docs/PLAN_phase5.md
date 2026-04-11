# Phase 5 세부 기획안

> 대상: 블로그 플랫폼 변환 및 자동화 준비
> 신규 파일: visualization/blog_formatter.py

---

## 1. blog_formatter.py 역할

HTML 리포트 → 블로그 플랫폼 게시 가능한 형태로 변환.

### 지원 기능
1. **차트 이미지 추출**: Plotly HTML의 chart-container를 PNG로 렌더링 (kaleido 필요)
   - kaleido 없으면 HTML 임베드 방식으로 fallback
2. **마크다운 변환**: 테이블/텍스트 → 마크다운 (티스토리/Velog 용)
3. **OG 메타 태그 삽입**: title, description, og:image 자동 생성
4. **요약 섹션 자동 추출**: 리포트에서 핵심 수치만 추출 → 블로그 서문

### 출력 형식
- `reports/blog/{date}/post.html` — 블로그 직접 붙여넣기용
- `reports/blog/{date}/summary.md` — 서문/요약 마크다운

---

## 2. 함수 목록

| 함수 | 설명 |
|------|------|
| `extract_report_summary(report_path)` | HTML 리포트에서 핵심 수치 추출 |
| `add_og_meta(html, title, desc, image_url)` | OG 메타 태그 삽입 |
| `format_for_blog(report_path, platform)` | 통합 변환 함수 |
| `generate_post_summary(master, date)` | 오늘의 핵심 수치 마크다운 생성 |

---

## 3. 플랫폼별 처리

| 플랫폼 | 방식 |
|--------|------|
| 티스토리 | HTML 직접 게시 (스킨 호환 CSS 추가) |
| Velog | 마크다운 변환 (차트는 이미지 링크) |
| GitHub Pages | HTML 그대로 사용 |
