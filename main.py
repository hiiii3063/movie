
# ============================================
# 어제의 박스오피스 → 날짜 선택형 박스오피스
# KOBIS 공식 API 사용
# ============================================

import datetime
import re
from urllib.parse import urljoin

import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------
# 1. 페이지 설정
# --------------------------------------------
st.set_page_config(
    page_title="박스오피스 시네마",
    page_icon="🎬",
    layout="wide"
)

# --------------------------------------------
# 2. 어두운 영화관 테마
# --------------------------------------------
st.markdown("""
<style>
    .stApp {
        background-color: #101014;
        color: #F5F5F5;
    }

    h1, h2, h3 {
        color: #FFFFFF !important;
    }

    .movie-subtitle {
        color: #B8B8C5;
        font-size: 15px;
    }

    div[data-testid="stMetric"] {
        background-color: #202027;
        border: 1px solid #393943;
        padding: 22px 20px;
        border-radius: 14px;
    }

    div[data-testid="stMetricLabel"] {
        color: #C5C5D0;
    }

    div[data-testid="stMetricValue"] {
        color: #FF4B5C;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #393943;
        border-radius: 10px;
    }

    .stButton > button {
        background-color: #D7263D;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: bold;
    }

    hr {
        border-color: #393943;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------
# 3. API 주소 및 한국 시간 설정
# --------------------------------------------
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/"
    "webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

KOBIS_SITE = "https://www.kobis.or.kr"

# 서버의 시간대와 관계없이 한국 시간으로 날짜를 계산합니다.
KST = datetime.timezone(datetime.timedelta(hours=9))
today_kst = datetime.datetime.now(KST).date()
yesterday = today_kst - datetime.timedelta(days=1)

# --------------------------------------------
# 4. 달력에서 조회 날짜 선택
# --------------------------------------------
st.title("🎬 박스오피스 시네마")
st.markdown(
    '<p class="movie-subtitle">'
    '원하는 날짜의 일별 영화 순위를 확인하세요.'
    '</p>',
    unsafe_allow_html=True
)

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    format="YYYY-MM-DD"
)

# 선택한 날짜를 KOBIS API 형식인 YYYYMMDD로 변환합니다.
target_date = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 기준일: {selected_date.strftime('%Y년 %m월 %d일')} · "
    f"오늘({today_kst.strftime('%Y년 %m월 %d일')}) 자료는 선택할 수 없습니다."
)

st.markdown("---")

# --------------------------------------------
# 5. KOBIS API 요청 함수
# --------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_boxoffice(date_text, api_key):
    """선택한 날짜의 박스오피스 데이터를 가져옵니다."""

    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_text
        },
        timeout=20
    )

    response.raise_for_status()
    return response.json()


# --------------------------------------------
# 6. 공식 KOBIS 사이트에서 포스터 찾기
# --------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_official_poster(movie_code):
    """
    KOBIS 공식 영화 상세 페이지에서 이미지 경로를 찾습니다.
    공식 사이트에서 찾지 못하면 외부 이미지로 대체하지 않습니다.
    """

    detail_url = (
        f"{KOBIS_SITE}/kobis/business/mast/mvie/"
        f"searchMovieDtl.do?movieCd={movie_code}"
    )

    try:
        response = requests.get(
            detail_url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )
        response.raise_for_status()

        html = response.text

        # HTML에 포함된 이미지 주소를 찾습니다.
        # 상대 주소와 절대 주소를 모두 처리합니다.
        candidates = re.findall(
            r"""(?:src|data-src|content)\s*=\s*["']([^"']+)["']""",
            html,
            flags=re.IGNORECASE
        )

        candidates += re.findall(
            r"""https?://[^"' ]+|/common/mast/movie/[^"' ]+""",
            html,
            flags=re.IGNORECASE
        )

        poster_candidates = []

        for candidate in candidates:
            candidate = candidate.replace("&amp;", "&")

            # KOBIS 공식 영화 이미지 경로만 허용합니다.
            if "/common/mast/movie/" not in candidate:
                continue

            # 썸네일보다 원본 포스터 경로를 우선합니다.
            if "/thumb/" in candidate or "thn_" in candidate.lower():
                continue

            image_url = urljoin(KOBIS_SITE, candidate)

            if image_url.startswith(
                "https://www.kobis.or.kr/common/mast/movie/"
            ):
                if image_url not in poster_candidates:
                    poster_candidates.append(image_url)

        # 실제 이미지 응답인지 확인합니다.
        for image_url in poster_candidates:
            try:
                image_response = requests.get(
                    image_url,
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"}
                )

                content_type = image_response.headers.get(
                    "Content-Type", ""
                ).lower()

                if (
                    image_response.status_code == 200
                    and content_type.startswith("image/")
                    and len(image_response.content) > 1000
                ):
                    return image_url

            except requests.exceptions.RequestException:
                continue

    except requests.exceptions.RequestException:
        pass

    # 공식 이미지 확인에 실패하면 임의의 이미지를 사용하지 않습니다.
    return None


# --------------------------------------------
# 7. 인증키 불러오기
# --------------------------------------------
try:
    api_key = st.secrets["KOBIS_KEY"]

    if not str(api_key).strip():
        st.error(
            "KOBIS 인증키가 비어 있습니다. "
            "앱 설정의 Secrets에서 KOBIS_KEY를 확인하세요."
        )
        st.stop()

except (KeyError, FileNotFoundError):
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 Settings → Secrets에 "
        'KOBIS_KEY = "발급받은 인증키"를 등록하세요.'
    )
    st.stop()


# --------------------------------------------
# 8. 선택한 날짜의 박스오피스 요청
# --------------------------------------------
try:
    with st.spinner("영화 순위와 정보를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_date, api_key)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 초과되었습니다. "
        "잠시 후 다시 시도하세요."
    )
    st.stop()

except requests.exceptions.HTTPError as error:
    st.error(f"API HTTP 오류: {error}")
    st.info("KOBIS 서버 상태와 요청 주소를 확인하세요.")
    st.stop()

except requests.exceptions.RequestException as error:
    st.error(f"KOBIS 서버 연결에 실패했습니다: {error}")
    st.info("인터넷 연결 또는 KOBIS 서버 상태를 확인하세요.")
    st.stop()

except ValueError:
    st.error("API 응답을 JSON으로 읽을 수 없습니다.")
    st.info("KOBIS 서버의 응답 상태를 확인하세요.")
    st.stop()


# --------------------------------------------
# 9. API 자체 오류 확인
# --------------------------------------------
if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.stop()

# 인증키가 잘못되어도 HTTP 200일 수 있으므로 따로 검사합니다.
if "faultInfo" in data:
    fault = data.get("faultInfo", {})

    if isinstance(fault, dict):
        error_code = fault.get("errorCode", "")
        error_message = fault.get(
            "message",
            "오류 상세 메시지가 없습니다."
        )
    else:
        error_code = ""
        error_message = str(fault)

    st.error("KOBIS API가 오류 응답을 반환했습니다.")

    if error_code:
        st.write(f"오류 코드: {error_code}")

    st.write(f"오류 내용: {error_message}")

    st.info(
        "Secrets의 KOBIS_KEY, 인증키 발급 상태, "
        "요청 날짜와 API 주소를 확인하세요."
    )
    st.stop()


# --------------------------------------------
# 10. 응답에서 영화 목록 추출
# --------------------------------------------
box_office_result = data.get("boxOfficeResult")

if not isinstance(box_office_result, dict):
    st.error("박스오피스 결과를 찾을 수 없습니다.")
    st.info("KOBIS API 응답 구조를 확인하세요.")
    st.stop()

movies = box_office_result.get("dailyBoxOfficeList", [])

# 선택한 날짜에 영화 목록이 없다면 지정한 문구를 표시합니다.
if not movies:
    st.warning("그날은 아직 집계 전입니다")
    st.info(
        "선택한 날짜의 자료가 아직 집계되지 않았거나 "
        "해당 날짜에 제공되는 박스오피스 자료가 없을 수 있습니다. "
        "KOBIS 공식 사이트에서 확인한 뒤 다시 시도하세요."
    )
    st.link_button(
        "KOBIS 공식 사이트 확인하기",
        "https://www.kobis.or.kr/"
    )
    st.stop()


# --------------------------------------------
# 11. 표와 그래프용 데이터 정리
# --------------------------------------------
df = pd.DataFrame(movies)

# 필요한 항목이 누락되어도 앱이 중단되지 않도록 기본값을 설정합니다.
required_columns = {
    "rank": "0",
    "rankInten": "0",
    "rankOldAndNew": "",
    "movieCd": "",
    "movieNm": "영화명 없음",
    "openDt": "",
    "audiCnt": "0",
    "audiAcc": "0",
    "scrnCnt": "0"
}

for column, default_value in required_columns.items():
    if column not in df.columns:
        df[column] = default_value

# 숫자형 문자열을 실제 정수로 변환합니다.
number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for column in number_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)

df["movieNm"] = df["movieNm"].fillna("영화명 없음").astype(str)
df["openDt"] = df["openDt"].fillna("").astype(str)
df["movieCd"] = df["movieCd"].fillna("").astype(str)

df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------
# 12. 순위 변동과 트로피 표시
# --------------------------------------------
def rank_change_text(row):
    """
    KOBIS rankInten을 이용해 순위 변동을 표시합니다.
    양수: 순위 상승 / 음수: 순위 하락 / 0: 변동 없음
    """

    change = int(row["rankInten"])
    status = str(row["rankOldAndNew"]).upper()

    if status == "NEW":
        return "신규 진입"

    if change > 0:
        return f"▲ {change}"

    if change < 0:
        return f"▼ {abs(change)}"

    return "—"


# 누적관객이 100만 명을 초과하면 영화명 옆에 트로피를 붙입니다.
df["표시 영화명"] = df.apply(
    lambda row: (
        f"🏆 {row['movieNm']}"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"]
    ),
    axis=1
)

df["순위 변동"] = df.apply(rank_change_text, axis=1)


# --------------------------------------------
# 13. 1위 영화와 공식 포스터
# --------------------------------------------
first_movie = df.iloc[0]

st.markdown("---")
st.subheader("🏆 오늘의 주인공")

poster_col, info_col = st.columns([1, 2])

with poster_col:
    movie_code = first_movie["movieCd"]

    if movie_code:
        with st.spinner("KOBIS 공식 포스터를 확인하는 중입니다..."):
            poster_url = fetch_official_poster(movie_code)

        if poster_url:
            st.image(
                poster_url,
                caption="출처: KOBIS 공식 영화 정보",
                use_container_width=True
            )
        else:
            st.warning(
                "KOBIS 공식 사이트에서 확인 가능한 포스터를 "
                "찾지 못했습니다. 다른 사이트의 이미지로 대체하지 않았습니다."
            )
            st.link_button(
                "KOBIS에서 영화 확인하기",
                "https://www.kobis.or.kr/kobis/business/mast/mvie/"
                "searchMovieList.do"
            )
    else:
        st.warning("영화 코드가 없어 공식 포스터를 조회할 수 없습니다.")

with info_col:
    st.markdown(f"### 1위 | {first_movie['movieNm']}")
    st.caption(
        f"개봉일: {first_movie['openDt'] or '정보 없음'}"
    )

    card1, card2, card3 = st.columns(3)

    with card1:
        st.metric(
            "당일 관객수",
            f"{first_movie['audiCnt']:,}명"
        )

    with card2:
        st.metric(
            "누적 관객수",
            f"{first_movie['audiAcc']:,}명"
        )

    with card3:
        st.metric(
            "스크린수",
            f"{first_movie['scrnCnt']:,}개"
        )


# --------------------------------------------
# 14. 전체 박스오피스 표
# --------------------------------------------
st.markdown("---")
st.subheader("📋 일별 박스오피스 순위")

table_df = df[
    [
        "rank",
        "순위 변동",
        "표시 영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

table_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

table_df["개봉일"] = table_df["개봉일"].replace("", "-")

# 숫자에 천 단위 쉼표를 적용합니다.
for column in ["관객수", "누적관객", "스크린수"]:
    table_df[column] = table_df[column].map(
        lambda value: f"{value:,}"
    )

# 순위 상승은 빨간색, 하락은 파란색으로 표시합니다.
def style_rank_change(value):
    if str(value).startswith("▲"):
        return "color: #FF4B5C; font-weight: bold;"
    elif str(value).startswith("▼"):
        return "color: #55A7FF; font-weight: bold;"
    elif value == "신규 진입":
        return "color: #E7C66A; font-weight: bold;"
    return "color: #B8B8C5;"

styled_table = table_df.style.map(
    style_rank_change,
    subset=["순위 변동"]
)

st.dataframe(
    styled_table,
    hide_index=True,
    use_container_width=True
)

st.caption(
    "▲ 순위 상승 · ▼ 순위 하락 · — 변동 없음 · "
    "신규 진입은 별도 표시"
)
st.caption("🏆 누적 관객수가 100만 명을 초과한 영화")


# --------------------------------------------
# 15. 관객수 상위 5편 막대그래프
# --------------------------------------------
st.markdown("---")
st.subheader("📊 관객수 TOP 5")
st.caption("막대가 길수록 선택한 날짜의 관객수가 많습니다.")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .sort_values("audiCnt", ascending=True)
    .copy()
)

fig = px.bar(
    top5,
    x="audiCnt",
    y="표시 영화명",
    orientation="h",
    text="audiCnt",
    labels={
        "audiCnt": "관객수(명)",
        "표시 영화명": "영화명"
    },
    color_discrete_sequence=["#E63950"]
)

fig.update_traces(
    texttemplate="%{text:,.0f}명",
    textposition="outside",
    cliponaxis=False,
    hovertemplate=(
        "<b>%{y}</b><br>"
        "관객수: %{x:,.0f}명"
        "<extra></extra>"
    )
)

fig.update_layout(
    paper_bgcolor="#101014",
    plot_bgcolor="#101014",
    font=dict(color="#F5F5F5"),
    xaxis=dict(
        title="관객수(명)",
        gridcolor="#393943",
        tickformat=","
    ),
    yaxis=dict(
        title="",
        showgrid=False
    ),
    margin=dict(l=10, r=70, t=20, b=20),
    height=380
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# --------------------------------------------
# 16. 출처
# --------------------------------------------
st.markdown("---")
st.caption(
    "박스오피스 데이터: 영화관입장권통합전산망(KOBIS) Open API"
)
st.caption(
    "포스터 조회: KOBIS 공식 영화 정보 페이지. "
    "공식 포스터를 확인하지 못하면 이미지를 표시하지 않습니다."
)
