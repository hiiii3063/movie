
# ============================================
# 어제의 박스오피스 - KOBIS 일별 박스오피스 앱
# 초보자도 이해할 수 있도록 주석을 달았습니다.
# ============================================

import datetime
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

# 2. 영화관 분위기의 어두운 테마 설정
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

    .stButton > button:hover {
        background-color: #A91D30;
        color: white;
    }

    hr {
        border-color: #393943;
    }
</style>
""", unsafe_allow_html=True)

# 3. KOBIS API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/"
    "webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

# 4. 한국 시간 기준으로 어제 날짜 계산
# 배포 서버가 다른 시간대를 사용해도 한국 날짜를 기준으로 계산합니다.
KST = datetime.timezone(datetime.timedelta(hours=9))
today_kst = datetime.datetime.now(KST).date()
yesterday = today_kst - datetime.timedelta(days=1)

# API는 날짜를 YYYYMMDD 형식으로 요구합니다.
target_date = yesterday.strftime("%Y%m%d")

# 5. API에서 영화 정보를 가져오는 함수
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_boxoffice(date_text, api_key):
    """KOBIS API를 호출하고 JSON 응답을 반환합니다."""

    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_text
        },
        timeout=15
    )

    # HTTP 오류가 발생하면 예외를 발생시킵니다.
    response.raise_for_status()

    # 응답을 JSON으로 변환합니다.
    return response.json()


# 6. 앱 제목과 조회 날짜 표시
st.title("🎬 어제의 박스오피스")
st.markdown(
    '<p class="movie-subtitle">'
    'KOBIS 공식 일별 박스오피스 · 한국 시간 기준'
    '</p>',
    unsafe_allow_html=True
)

st.markdown("---")

st.write(
    f"**조회 날짜:** {yesterday.strftime('%Y년 %m월 %d일')}"
)

st.caption(
    "관객수와 순위는 해당 날짜의 집계 자료입니다. "
    "최신 집계 상황에 따라 결과가 달라질 수 있습니다."
)

# 7. 인증키를 Streamlit 비밀 금고에서 불러오기
# 인증키를 코드에 직접 입력하지 않습니다.
try:
    api_key = st.secrets["KOBIS_KEY"]

    if not str(api_key).strip():
        st.error(
            "인증키가 비어 있습니다. "
            "Streamlit Cloud의 Settings → Secrets에서 "
            "KOBIS_KEY 값을 확인해 주세요."
        )
        st.stop()

except (KeyError, FileNotFoundError):
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        'KOBIS_KEY = "발급받은 인증키" 형식으로 등록해 주세요.'
    )
    st.stop()

# 8. 데이터 요청 및 통신 오류 처리
try:
    with st.spinner("어제의 영화 순위를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_date, api_key)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 초과되었습니다. "
        "잠시 후 새로고침해 주세요."
    )
    st.stop()

except requests.exceptions.HTTPError as error:
    st.error(
        f"API 서버가 HTTP 오류를 반환했습니다: {error}"
    )
    st.info(
        "인터넷 연결, API 주소, KOBIS 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as error:
    st.error(
        f"KOBIS 서버에 연결하지 못했습니다: {error}"
    )
    st.info(
        "Streamlit Cloud의 인터넷 연결이나 KOBIS 서버 상태를 확인해 주세요."
    )
    st.stop()

except ValueError:
    st.error(
        "API 응답을 JSON으로 읽을 수 없습니다. "
        "KOBIS 서버가 정상적인 응답을 반환했는지 확인해 주세요."
    )
    st.stop()

# 9. 인증키 오류 등 API 자체의 오류 확인
# KOBIS는 HTTP 200이어도 faultInfo를 반환할 수 있습니다.
if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.info("KOBIS API의 응답 형식과 서버 상태를 확인해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo", {})

    if isinstance(fault, dict):
        error_message = fault.get(
            "message",
            "오류 상세 메시지가 제공되지 않았습니다."
        )
        error_code = fault.get("errorCode", "")
    else:
        error_message = str(fault)
        error_code = ""

    st.error("KOBIS API에서 오류 응답을 반환했습니다.")

    if error_code:
        st.write(f"**오류 코드:** {error_code}")

    st.write(f"**오류 내용:** {error_message}")

    st.info(
        "확인할 항목\n\n"
        "1. Secrets에 등록한 KOBIS_KEY가 정확한지 확인하세요.\n"
        "2. 인증키가 정상적으로 발급되었는지 확인하세요.\n"
        "3. API 요청 주소와 조회 날짜 형식이 올바른지 확인하세요."
    )
    st.stop()

# 10. 영화 목록 추출
box_office_result = data.get("boxOfficeResult")

if not isinstance(box_office_result, dict):
    st.error("박스오피스 결과를 찾을 수 없습니다.")
    st.info(
        "KOBIS API 응답 구조가 변경되었거나 "
        "정상적인 결과가 반환되지 않았을 수 있습니다."
    )
    st.stop()

movies = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있을 때 안내
if not movies:
    st.warning("해당 날짜의 영화 목록이 비어 있습니다.")
    st.info(
        "다음 항목을 확인해 주세요.\n\n"
        "1. 어제 날짜의 박스오피스 집계가 완료되었는지 확인하세요.\n"
        "2. KOBIS 공식 사이트에서 같은 날짜의 자료를 조회해 보세요.\n"
        "3. 잠시 후 새로고침하여 다시 요청해 보세요."
    )
    st.stop()

# 11. 표와 그래프에 사용하도록 데이터를 정리
df = pd.DataFrame(movies)

# 혹시 일부 항목이 누락되더라도 앱이 중단되지 않도록
# 필요한 열을 먼저 확인하고 없으면 기본값을 넣습니다.
required_columns = {
    "rank": "0",
    "movieNm": "영화명 없음",
    "openDt": "",
    "audiCnt": "0",
    "audiAcc": "0",
    "scrnCnt": "0"
}

for column, default_value in required_columns.items():
    if column not in df.columns:
        df[column] = default_value

# API에서 숫자가 문자열로 오므로 실제 숫자로 변환합니다.
number_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]

for column in number_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)

# 순위가 낮은 숫자부터 정렬합니다.
df = df.sort_values("rank", ascending=True).reset_index(drop=True)

# 12. 1위 영화 정보 표시
first_movie = df.iloc[0]

st.markdown("---")
st.subheader("🏆 오늘의 주인공")
st.markdown(f"### 1위 | {first_movie['movieNm']}")

# 세 개의 지표 카드를 가로로 배치합니다.
card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="어제 관객수",
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

# 13. 전체 박스오피스 순위표
st.markdown("---")
st.subheader("📋 일별 박스오피스 순위")

table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 화면에 표시할 한국어 열 이름
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 날짜가 없는 영화는 '-'로 표시합니다.
table_df["개봉일"] = table_df["개봉일"].replace("", "-")

# 숫자에 천 단위 쉼표를 적용합니다.
for column in ["관객수", "누적관객", "스크린수"]:
    table_df[column] = table_df[column].map(
        lambda value: f"{value:,}"
    )

st.dataframe(
    table_df,
    hide_index=True,
    use_container_width=True
)

# 14. 관객수 상위 5편 막대그래프
st.markdown("---")
st.subheader("📊 관객수 TOP 5")
st.caption("막대가 길수록 해당 날짜의 관객수가 많습니다.")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .sort_values("audiCnt", ascending=True)
    .copy()
)

# 어두운 영화관 테마에 맞춰 그래프를 구성합니다.
fig = px.bar(
    top5,
    x="audiCnt",
    y="movieNm",
    orientation="h",
    text="audiCnt",
    labels={
        "audiCnt": "관객수(명)",
        "movieNm": "영화명"
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
    font=dict(
        color="#F5F5F5",
        family="Arial"
    ),
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

# 15. 하단 출처 표시
st.markdown("---")
st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일별 박스오피스 Open API"
)
st.caption(
    "※ 관객수와 순위는 KOBIS 집계 결과를 기준으로 합니다."
)
