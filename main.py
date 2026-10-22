
# ============================================
# 박스오피스 시네마
# KOBIS 공식 API를 이용한 날짜별 영화 순위 앱
# ============================================

import datetime
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
# 3. KOBIS API 주소 및 한국 시간 설정
# --------------------------------------------
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/"
    "webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

# 한국 시간 기준으로 오늘과 어제를 계산합니다.
KST = datetime.timezone(datetime.timedelta(hours=9))
today_kst = datetime.datetime.now(KST).date()
yesterday = today_kst - datetime.timedelta(days=1)

# --------------------------------------------
# 4. 제목 및 날짜 선택
# --------------------------------------------
st.title("🎬 박스오피스 시네마")

st.markdown(
    '<p class="movie-subtitle">'
    '원하는 날짜의 일별 영화 순위를 확인하세요.'
    '</p>',
    unsafe_allow_html=True
)

# 오늘은 집계 전이므로 어제까지만 선택할 수 있습니다.
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    min_value=datetime.date(2004, 1, 1),
    max_value=yesterday,
    format="YYYY-MM-DD"
)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환합니다.
target_date = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {selected_date.strftime('%Y년 %m월 %d일')} · "
    f"선택 가능 기간: 2004년 1월 1일 ~ "
    f"{yesterday.strftime('%Y년 %m월 %d일')}"
)

st.markdown("---")

# --------------------------------------------
# 5. API 요청 함수
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

    # HTTP 오류가 있으면 예외를 발생시킵니다.
    response.raise_for_status()

    # 응답 JSON을 반환합니다.
    return response.json()


# --------------------------------------------
# 6. 인증키 불러오기
# --------------------------------------------
try:
    api_key = st.secrets["KOBIS_KEY"]

    if not str(api_key).strip():
        st.error(
            "KOBIS 인증키가 비어 있습니다. "
            "Streamlit Cloud의 Settings → Secrets에서 "
            "KOBIS_KEY를 확인하세요."
        )
        st.stop()

except (KeyError, FileNotFoundError):
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 Secrets에 다음 형식으로 등록하세요.\n\n"
        'KOBIS_KEY = "발급받은 인증키"'
    )
    st.stop()


# --------------------------------------------
# 7. API 요청 및 통신 오류 처리
# --------------------------------------------
try:
    with st.spinner("박스오피스 정보를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_date, api_key)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 초과되었습니다. "
        "잠시 후 다시 시도하세요."
    )
    st.stop()

except requests.exceptions.HTTPError as error:
    st.error(f"KOBIS API HTTP 오류: {error}")
    st.info("API 주소와 KOBIS 서버 상태를 확인하세요.")
    st.stop()

except requests.exceptions.RequestException as error:
    st.error(f"KOBIS 서버에 연결하지 못했습니다: {error}")
    st.info("인터넷 연결 또는 KOBIS 서버 상태를 확인하세요.")
    st.stop()

except ValueError:
    st.error("API 응답을 JSON으로 읽을 수 없습니다.")
    st.info("KOBIS 서버의 응답 상태를 확인하세요.")
    st.stop()


# --------------------------------------------
# 8. API 자체 오류 확인
# --------------------------------------------
# 인증키가 틀려도 HTTP 상태 코드가 200일 수 있습니다.
# 따라서 faultInfo 항목도 확인합니다.
if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.stop()

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

    st.error("KOBIS API에서 오류 응답을 반환했습니다.")

    if error_code:
        st.write(f"오류 코드: {error_code}")

    st.write(f"오류 내용: {error_message}")

    st.info(
        "확인할 항목\n\n"
        "1. KOBIS_KEY가 정확한지 확인하세요.\n"
        "2. 인증키가 정상적으로 발급되었는지 확인하세요.\n"
        "3. 요청 날짜와 API 주소를 확인하세요."
    )
    st.stop()


# --------------------------------------------
# 9. 영화 목록 추출
# --------------------------------------------
box_office_result = data.get("boxOfficeResult")

if not isinstance(box_office_result, dict):
    st.error("박스오피스 결과를 찾을 수 없습니다.")
    st.info("KOBIS API의 응답 구조를 확인하세요.")
    st.stop()

movies = box_office_result.get("dailyBoxOfficeList", [])

# 선택한 날짜에 영화 목록이 없으면 안내합니다.
if not movies:
    st.warning("그날은 아직 집계 전입니다")
    st.info(
        "선택한 날짜의 자료가 아직 집계되지 않았거나 "
        "해당 날짜의 박스오피스 자료가 제공되지 않을 수 있습니다.\n\n"
        "KOBIS 공식 사이트에서 해당 날짜를 확인한 뒤 "
        "다시 조회해 주세요."
    )

    st.link_button(
        "KOBIS 공식 사이트 확인하기",
        "https://www.kobis.or.kr/"
    )
    st.stop()


# --------------------------------------------
# 10. 데이터 정리
# --------------------------------------------
df = pd.DataFrame(movies)

# 필요한 항목이 없는 경우 기본값을 넣습니다.
required_columns = {
    "rank": "0",
    "rankInten": "0",
    "rankOldAndNew": "",
    "movieNm": "영화명 없음",
    "openDt": "",
    "audiCnt": "0",
    "audiAcc": "0",
    "scrnCnt": "0"
}

for column, default_value in required_columns.items():
    if column not in df.columns:
        df[column] = default_value

# API에서 숫자가 문자열로 오므로 정수로 변환합니다.
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
df["rankOldAndNew"] = (
    df["rankOldAndNew"].fillna("").astype(str)
)

# 순위가 높은 영화부터 정렬합니다.
df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------
# 11. 순위 변동 표시
# --------------------------------------------
def rank_change_text(row):
    """전날 대비 순위 변동을 문자로 표시합니다."""

    change = int(row["rankInten"])
    status = row["rankOldAndNew"].upper()

    # 신규 진입 영화는 별도로 표시합니다.
    if status == "NEW":
        return "신규 진입"

    # 양수는 순위 상승, 음수는 순위 하락입니다.
    if change > 0:
        return f"▲ {change}"

    if change < 0:
        return f"▼ {abs(change)}"

    return "—"


df["순위 변동"] = df.apply(rank_change_text, axis=1)

# 누적관객수가 100만 명을 초과하면 트로피를 표시합니다.
df["표시 영화명"] = df.apply(
    lambda row: (
        f"🏆 {row['movieNm']}"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"]
    ),
    axis=1
)


# --------------------------------------------
# 12. 1위 영화 지표 카드
# --------------------------------------------
first_movie = df.iloc[0]

st.markdown("---")
st.subheader("🏆 오늘의 주인공")
st.markdown(f"### 1위 | {first_movie['표시 영화명']}")

if first_movie["openDt"]:
    st.caption(f"개봉일: {first_movie['openDt']}")
else:
    st.caption("개봉일 정보 없음")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="당일 관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )

with card2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명"
    )

with card3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개"
    )


# --------------------------------------------
# 13. 전체 박스오피스 순위표
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

# 숫자에 천 단위 쉼표를 표시합니다.
for column in ["관객수", "누적관객", "스크린수"]:
    table_df[column] = table_df[column].map(
        lambda value: f"{value:,}"
    )

# 상승은 빨간색, 하락은 파란색으로 표시합니다.
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
    "▲ 순위 상승 · ▼ 순위 하락 · — 변동 없음 · 신규 진입"
)
st.caption("🏆 누적관객수가 100만 명을 초과한 영화")


# --------------------------------------------
# 14. 관객수 TOP 5 막대그래프
# --------------------------------------------
st.markdown("---")
st.subheader("📊 관객수 TOP 5")
st.caption("막대가 길수록 해당 날짜의 관객수가 많습니다.")

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
# 15. 데이터 출처
# --------------------------------------------
st.markdown("---")

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일별 박스오피스 Open API"
)

st.caption(
    "관객수와 순위는 선택한 날짜의 KOBIS 집계 결과를 기준으로 합니다."
)
