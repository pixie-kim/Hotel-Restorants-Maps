import os
import json
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# ─────────────────────────────────────────────
# 1. 파일 경로 및 기본 환경 설정
# ─────────────────────────────────────────────
SHP_PATH  = "N3A_G0100000.shp"
DATA_FILE = "companies.json"

st.set_page_config(page_title="행정구역 업체관리", layout="wide", initial_sidebar_state="collapsed")

# ─────────────────────────────────────────────
# 2. GIS 데이터 로드 및 표준 GeoJSON 변환 (메모리 유실 방지)
# ─────────────────────────────────────────────
@st.cache_data
def load_geojson_data():
    if not os.path.exists(SHP_PATH):
        st.error(f"SHP 파일을 찾을 수 없습니다: {SHP_PATH}")
        st.stop()
    
    # SHP 읽기 및 좌표계 변환 (WGS84 표준 위경도)
    gdf = gpd.read_file(SHP_PATH, encoding="cp949")
    if gdf.crs is None:
        gdf.crs = "EPSG:5179"
    gdf = gdf.to_crs(epsg=4326)
    
    # 공백 제거 및 결측치 처리
    gdf["NAME"] = gdf["NAME"].astype(str).str.strip()
    gdf = gdf.dropna(subset=["NAME"])
    
    # [핵심] 꼬임 방지를 위해 순수 파이썬 dict(GeoJSON) 형태로 캐싱 전환
    return json.loads(gdf.to_json())

# 지도 데이터 포맷 확보
geojson_data = load_geojson_data()

# 선택 가능한 행정구역 목록 추출
all_region_names = sorted(list(set(
    feature['properties']['NAME'] 
    for feature in geojson_data['features'] 
    if feature['properties'].get('NAME')
)))

# ─────────────────────────────────────────────
# 3. 사용자 데이터 데이터베이스(JSON) 관리
# ─────────────────────────────────────────────
if "region_data" not in st.session_state:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                st.session_state.region_data = json.load(f)
        except Exception:
            st.session_state.region_data = {}
    else:
        st.session_state.region_data = {}

if "selected_region" not in st.session_state or st.session_state.selected_region not in all_region_names:
    st.session_state.selected_region = all_region_names[0] if all_region_names else ""

# ─────────────────────────────────────────────
# 4. 메인 대시보드 화면 레이아웃
# ─────────────────────────────────────────────
st.title("🗺️ 대한민국 행정구역 업체관리 시스템")

tab_map, tab_list = st.tabs(["📍 지도 및 정보 관리", "📋 전체 등록 목록"])

with tab_map:
    col_map, col_panel = st.columns([3, 2], gap="large")

    with col_map:
        st.markdown("#### 🎯 행정구역 검색 및 선택")
        
        # 검색 지원 드롭다운과 동기화
        chosen = st.selectbox(
            "관리할 지역을 선택하세요", 
            all_region_names, 
            index=all_region_names.index(st.session_state.selected_region) if st.session_state.selected_region in all_region_names else 0
        )
        if chosen != st.session_state.selected_region:
            st.session_state.selected_region = chosen
            st.rerun()

        # 대한민국 중심부를 기본 축으로 지도 레이아웃 빌드
        m = folium.Map(location=[36.3, 127.8], zoom_start=8, tiles="OpenStreetMap")
        
        # 선택 구역 하이라이팅 스타일 함수
        def region_style(feature):
            curr_name = feature['properties'].get('NAME', '')
            is_target = (curr_name == st.session_state.selected_region)
            return {
                'fillColor': '#ffb6c1' if is_target else '#4361ee',
                'color': '#dc325a' if is_target else '#4361ee',
                'weight': 3 if is_target else 1,
                'fillOpacity': 0.6 if is_target else 0.15
            }

        # 정제된 순수 GeoJSON 레이어 주입
        folium.GeoJson(
            geojson_data,
            style_function=region_style,
            tooltip=folium.GeoJsonTooltip(fields=["NAME"], aliases=["지역명:"])
        ).add_to(m)
        
        # 인터랙티브 맵 렌더링
        st_folium(m, width="100%", height=580, key="stable_geojson_map")

    with col_panel:
        region = st.session_state.selected_region
        st.subheader(f"📌 {region} 관리 판넬")

        if region not in st.session_state.region_data:
            st.session_state.region_data[region] = []

        companies = st.session_state.region_data[region]

        # 데이터 입력 가젯 렌더링 루프
        to_delete = None
        for idx, company in enumerate(companies):
            with st.container():
                c_name = st.text_input("업체명 *", value=company.get("name", ""), key=f"n_{region}_{idx}")
                c_addr = st.text_input("상세 주소", value=company.get("address", ""), key=f"a_{region}_{idx}")
                c_phon = st.text_input("전화번호", value=company.get("phone", ""), key=f"p_{region}_{idx}")
                
                # 입력 상태 배열에 즉시 업데이트 보존
                st.session_state.region_data[region][idx] = {"name": c_name, "address": c_addr, "phone": c_phon}
                
                if st.button("🗑️ 제거", key=f"d_{region}_{idx}", use_container_width=True):
                    to_delete = idx
                st.markdown("---")

        if to_delete is not None:
            st.session_state.region_data[region].pop(to_delete)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.region_data, f, ensure_ascii=False, indent=4)
            st.rerun()

        b1, b2 = st.columns(2)
        with b1:
            if st.button("➕ 업체 추가", use_container_width=True):
                st.session_state.region_data[region].append({"name": "", "address": "", "phone": ""})
                st.rerun()
        with b2:
            if st.button("💾 최종 저장", type="primary", use_container_width=True):
                # 유효 데이터 필터링 후 영구 저장
                st.session_state.region_data[region] = [c for c in companies if c.get("name", "").strip()]
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.region_data, f, ensure_ascii=False, indent=4)
                st.success("데이터베이스에 반영되었습니다.")
                st.rerun()

# ─────────────────────────────────────────────
# 5. 데이터 그리드 및 통합 내보내기 탭
# ─────────────────────────────────────────────
with tab_list:
    st.markdown("#### 📋 등록된 전체 업체 데이터베이스")
    all_data = []
    for r, comps in st.session_state.region_data.items():
        for c in comps:
            if c.get("name", "").strip():
                all_data.append({"행정구역": r, "업체명": c["name"], "주소": c.get("address",""), "전화번호": c.get("phone","")})
                
    if all_data:
        df = pd.DataFrame(all_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 전체 데이터 CSV 다운로드", 
            data=df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), 
            file_name="company_list.csv", 
            mime="text/csv"
        )
    else:
        st.info("현재 등록된 업체 정보가 존재하지 않습니다.")
