"""주요 도시 좌표 및 메타 정보."""

CITIES: dict[str, dict] = {
    # 국내
    "seoul":     {"lat": 37.5665, "lon": 126.9780, "name_ko": "서울",     "timezone": "Asia/Seoul"},
    "busan":     {"lat": 35.1796, "lon": 129.0756, "name_ko": "부산",     "timezone": "Asia/Seoul"},
    "incheon":   {"lat": 37.4563, "lon": 126.7052, "name_ko": "인천",     "timezone": "Asia/Seoul"},
    "daegu":     {"lat": 35.8714, "lon": 128.6014, "name_ko": "대구",     "timezone": "Asia/Seoul"},
    "daejeon":   {"lat": 36.3504, "lon": 127.3845, "name_ko": "대전",     "timezone": "Asia/Seoul"},
    "gwangju":   {"lat": 35.1595, "lon": 126.8526, "name_ko": "광주",     "timezone": "Asia/Seoul"},
    "suwon":     {"lat": 37.2636, "lon": 127.0286, "name_ko": "수원",     "timezone": "Asia/Seoul"},
    "jeju":      {"lat": 33.4996, "lon": 126.5312, "name_ko": "제주",     "timezone": "Asia/Seoul"},
    # 해외 주요
    "tokyo":     {"lat": 35.6762, "lon": 139.6503, "name_ko": "도쿄",     "timezone": "Asia/Tokyo"},
    "beijing":   {"lat": 39.9042, "lon": 116.4074, "name_ko": "베이징",   "timezone": "Asia/Shanghai"},
    "shanghai":  {"lat": 31.2304, "lon": 121.4737, "name_ko": "상하이",   "timezone": "Asia/Shanghai"},
    "newyork":   {"lat": 40.7128, "lon": -74.0060, "name_ko": "뉴욕",     "timezone": "America/New_York"},
    "london":    {"lat": 51.5074, "lon": -0.1278,  "name_ko": "런던",     "timezone": "Europe/London"},
    "paris":     {"lat": 48.8566, "lon": 2.3522,   "name_ko": "파리",     "timezone": "Europe/Paris"},
    "singapore": {"lat": 1.3521,  "lon": 103.8198, "name_ko": "싱가포르", "timezone": "Asia/Singapore"},
    "sydney":    {"lat": -33.8688,"lon": 151.2093, "name_ko": "시드니",   "timezone": "Australia/Sydney"},
    "dubai":     {"lat": 25.2048, "lon": 55.2708,  "name_ko": "두바이",   "timezone": "Asia/Dubai"},
}

# WMO 날씨 코드 → 한국어 설명
WMO_CODE: dict[int, str] = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
    45: "안개", 48: "상고대 안개",
    51: "이슬비(약)", 53: "이슬비", 55: "이슬비(강)",
    61: "비(약)", 63: "비", 65: "비(강)",
    71: "눈(약)", 73: "눈", 75: "눈(강)", 77: "싸락눈",
    80: "소나기(약)", 81: "소나기", 82: "소나기(강)",
    85: "눈 소나기(약)", 86: "눈 소나기(강)",
    95: "뇌우", 96: "뇌우+우박(약)", 99: "뇌우+우박(강)",
}
