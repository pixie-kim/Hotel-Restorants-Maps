import os
import json
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# ─────────────────────────────────────────────
# 1. 환경 설정 및 경로 정의
# ─────────────────────────────────────────────
SHP_PATH  = "N3A_G0100000.shp"
DATA_FILE = "companies.json"

st.set_page_config(page_title="행정구역 업체관리", layout="wide", initial_sidebar_state="collapsed")

# ─────────────────────────────────────────────
# 2. GIS 데이터 로드 (가장 가볍고 효율적인 원본 로드)
# ─────────────────────────────────────────────
def load_base_map():
    if not os.path.exists(SHP_PATH):
        st.error(f"파일을 찾을 수 없습니다: {SHP_PATH}")
        st.stop()
    
    # 원본 데이터 로드 (인코딩: cp949)
    gdf = gpd.read_file(SHP_PATH, encoding="cp949")
    
    # 대한민국 표준 위경도 좌표계(WGS84)로 변환
    if gdf.crs is None:
        gdf.crs = "EPSG:5179"
    gdf = gdf.to_crs(epsg=4326)
    
    return gdf

# 데이터 및 행정구역 이름 리스트 추출
gdf_regions = load_base_map()
all_region_names = sorted(gdf_regions["NAME"].dropna().unique().tolist())

# ─────────────────────────────────────────────
# 3. 사용자 데이터(JSON) 로드 및 상태 관리
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
    st.session_state.selected_region = all_region_names[0]

# ─────────────────────────────────────────────
# 4. 메인 UI 레이아웃
# ─────────────────────────────────────────────
st.title("🗺️ 대한민국 행정구역 업체관리 시스템")

tab_map, tab_list = st.tabs(["📍 지도 및 정보 관리", "📋 전체 등록 목록"])

with tab_map:
    col_map, col_panel = st.columns([3, 2], gap="large")

    with col_map:
        st.markdown("#### 🎯 행정구역 검색 및 선택")
        chosen = st.selectbox(
            "관리할 지역을 선택하세요", 
            all_region_names, 
            index=all_region_names.index(st.session_state.selected_region)
        )
        if chosen != st.session_state.selected_region:
            st.session_state.selected_region = chosen
            st.rerun()

        # 지도 중심점 계산 (전체 데이터 경계면 기준)
        bounds = gdf_regions.total_bounds
        m = folium.Map(
            location=[(bounds[1]+bounds[3])/2, (bounds[0]+bounds[2])/2], 
            zoom_start=8, 
            tiles="OpenStreetMap"
        )
        
        # 선택된 지역만 분홍색 하이라이트 스타일 정의
        def region_style(feature):
            curr_name = feature['properties'].get('NAME', '')
            is_target = (curr_name == st.session_state.selected_region)
            return {
                'fillColor': '#ffb6c1' if is_target else '#4361ee',
                'color': '#dc325a' if is_target else '#4361ee',
                'weight': 3 if is_target else 1,
                'fillOpacity': 0.6 if is_target else 0.1
            }

        folium.GeoJson(
            gdf_regions.__geo_interface__,
            style_function=region_style,
            tooltip=folium.GeoJsonTooltip(fields=["NAME"], aliases=["지역명:"])
        ).add_to(m)
        
        # 지도 컴포넌트 렌더링
        st_folium(m, width="100%", height=580, key="static_gis_map")

    with col_panel:
        region = st.session_state.selected_region
        st.subheader(f"📌 {region} 관리 판넬")

        if region not in st.session_state.region_data:
            st.session_state.region_data[region] = []

        companies = st.session_state.
