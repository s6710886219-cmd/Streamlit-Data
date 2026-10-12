"""
Dashboard ปริมาณขยะมูลฝอย กรมอุทยานแห่งชาติ สัตว์ป่า และพันธุ์พืช
แหล่งข้อมูล: https://data.go.th/dataset/gdpublish-69-dnp01-11-01

กราฟ 4 กราฟ
  1. Line chart   – แนวโน้มขยะรายเดือน (เกิดขึ้น / ใช้ประโยชน์ / ส่งกำจัด)
  2. Bar chart    – Top N หน่วยงานที่มีขยะมากที่สุด
  3. Donut chart  – สัดส่วนขยะแยกตามสังกัด
  4. Scatter plot – จำนวนคน vs ปริมาณขยะ ของแต่ละหน่วยงาน

Interactive widget 2 รายการ (อยู่ใน sidebar)
  1. st.multiselect   – เลือกสังกัด
  2. st.select_slider – เลือกช่วงเดือน
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# ตั้งค่าหน้าเว็บ
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Dashboard ปริมาณขยะมูลฝอย", page_icon="♻️", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

# ไฟล์ CSV ในโฟลเดอร์ data/ (ดาวน์โหลดจาก data.go.th) และ resource id สำหรับดึงผ่าน API ถ้าไม่มีไฟล์
SOURCES = {
    2568: ("waste_2568.csv", "d618f269-fc24-43b1-92fe-4fcc513fa579"),
    2569: ("waste_2569.csv", "d27c7f92-8268-4e0e-abf1-fafc44d6aec1"),
}
API_URL = "https://data.go.th/api/3/action/datastore_search"

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]

# ชื่อคอลัมน์หลักในชุดข้อมูล
COL_YEAR = "ปี"
COL_GROUP = "สังกัด"
COL_UNIT = "หน่วยงาน"
COL_MONTH = "เดือน"
COL_PEOPLE = "คนเฉลี่ย"
COL_DAYS = "วันทำงาน"
COL_TOTAL = "ขยะที่เกิดขึ้น (กก.)"
COL_REUSE = "ใช้ประโยชน์ (กก.)"
COL_DISPOSE = "ขยะที่ส่งกำจัด (กก.)"
NUMERIC_COLS = [COL_PEOPLE, COL_DAYS, COL_TOTAL, COL_REUSE, COL_DISPOSE]


# ---------------------------------------------------------------------------
# โหลดและทำความสะอาดข้อมูล
# ---------------------------------------------------------------------------
def read_csv_any_encoding(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp874", "tis-620"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"อ่านไฟล์ {path.name} ไม่ได้")


def fetch_from_api(resource_id: str) -> pd.DataFrame:
    resp = requests.get(API_URL, params={"resource_id": resource_id, "limit": 5000}, timeout=30)
    resp.raise_for_status()
    return pd.DataFrame(resp.json()["result"]["records"])


@st.cache_data(ttl=3600, show_spinner="กำลังโหลดข้อมูล...")
def load_data() -> pd.DataFrame:
    frames = []
    for year, (filename, resource_id) in SOURCES.items():
        path = DATA_DIR / filename
        try:
            df = read_csv_any_encoding(path) if path.exists() else fetch_from_api(resource_id)
        except Exception:
            continue  # ปีไหนโหลดไม่ได้ก็ข้ามไป
        df.columns = [str(c).strip() for c in df.columns]
        if COL_YEAR not in df.columns:
            df[COL_YEAR] = year
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True).drop(columns=["_id"], errors="ignore")

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False), errors="coerce"
            ).fillna(0)

    for col in (COL_GROUP, COL_UNIT, COL_MONTH):
        df[col] = df[col].astype(str).str.strip()

    df[COL_YEAR] = pd.to_numeric(df[COL_YEAR], errors="coerce").astype("Int64")
    df = df[df[COL_MONTH].isin(THAI_MONTHS)].copy()
    df["month_no"] = df[COL_MONTH].map({m: i + 1 for i, m in enumerate(THAI_MONTHS)})
    return df


df = load_data()

st.title("♻️ Dashboard ปริมาณขยะมูลฝอย")
st.caption(
    "กรมอุทยานแห่งชาติ สัตว์ป่า และพันธุ์พืช · ที่มา: "
    "[data.go.th](https://data.go.th/dataset/gdpublish-69-dnp01-11-01)"
)

if df.empty:
    st.error(
        "ไม่พบข้อมูล — ให้ดาวน์โหลดไฟล์ CSV จาก data.go.th แล้ววางไว้ที่ "
        "`data/waste_2568.csv` (และ `data/waste_2569.csv` ถ้ามี)"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar – Interactive widgets
# ---------------------------------------------------------------------------
st.sidebar.header("🔎 ตัวกรองข้อมูล")

years = sorted(df[COL_YEAR].dropna().unique().tolist())
if len(years) > 1:
    year = st.sidebar.selectbox("ปี พ.ศ.", years, index=len(years) - 1)
else:
    year = years[0]
data_year = df[df[COL_YEAR] == year]

# Widget 1: เลือกสังกัด
groups = sorted(data_year[COL_GROUP].unique().tolist())
selected_groups = st.sidebar.multiselect("1) เลือกสังกัด", options=groups, default=groups)

# Widget 2: เลือกช่วงเดือน
months_in_data = [m for m in THAI_MONTHS if m in set(data_year[COL_MONTH])]
if len(months_in_data) > 1:
    start_m, end_m = st.sidebar.select_slider(
        "2) เลือกช่วงเดือน",
        options=months_in_data,
        value=(months_in_data[0], months_in_data[-1]),
    )
else:
    start_m = end_m = months_in_data[0]
start_no, end_no = THAI_MONTHS.index(start_m) + 1, THAI_MONTHS.index(end_m) + 1

top_n = st.sidebar.slider("จำนวนหน่วยงานในกราฟ Top N", 5, 20, 10)

filtered = data_year[
    data_year[COL_GROUP].isin(selected_groups) & data_year["month_no"].between(start_no, end_no)
]

if filtered.empty:
    st.warning("ไม่มีข้อมูลตามตัวกรองที่เลือก กรุณาเลือกสังกัดอย่างน้อย 1 รายการ")
    st.stop()

st.sidebar.caption(f"ข้อมูลที่แสดง: {len(filtered):,} แถว จาก {len(data_year):,} แถว")

# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------
total = filtered[COL_TOTAL].sum()
reuse = filtered[COL_REUSE].sum()
dispose = filtered[COL_DISPOSE].sum()
person_days = (filtered[COL_PEOPLE] * filtered[COL_DAYS]).sum()
per_person_day = total / person_days if person_days else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("ขยะที่เกิดขึ้นรวม", f"{total:,.0f} กก.")
k2.metric("นำไปใช้ประโยชน์", f"{reuse:,.0f} กก.", f"{reuse / total:.1%} ของทั้งหมด" if total else None)
k3.metric("ส่งกำจัด", f"{dispose:,.0f} กก.", f"{dispose / total:.1%} ของทั้งหมด" if total else None,
          delta_color="inverse")
k4.metric("ขยะเฉลี่ยต่อคนต่อวัน", f"{per_person_day:.3f} กก.")

st.divider()

# ---------------------------------------------------------------------------
# กราฟ 1 & 2
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("📈 กราฟ 1: แนวโน้มขยะรายเดือน")
    monthly = (
        filtered.groupby(["month_no", COL_MONTH], as_index=False)[[COL_TOTAL, COL_REUSE, COL_DISPOSE]]
        .sum()
        .sort_values("month_no")
    )
    monthly_long = monthly.melt(
        id_vars=[COL_MONTH], value_vars=[COL_TOTAL, COL_REUSE, COL_DISPOSE],
        var_name="ประเภท", value_name="กิโลกรัม",
    )
    fig1 = px.line(
        monthly_long, x=COL_MONTH, y="กิโลกรัม", color="ประเภท", markers=True,
        color_discrete_sequence=["#2a6f97", "#52b788", "#e76f51"],
    )
    fig1.update_layout(xaxis_title=None, legend_title=None, legend=dict(orientation="h", y=-0.25),
                       hovermode="x unified")
    st.plotly_chart(fig1, width="stretch")

with c2:
    st.subheader(f"🏢 กราฟ 2: Top {top_n} หน่วยงานที่มีขยะมากที่สุด")
    by_unit = (
        filtered.groupby(COL_UNIT, as_index=False)[COL_TOTAL].sum()
        .nlargest(top_n, COL_TOTAL)
        .sort_values(COL_TOTAL)
    )
    fig2 = px.bar(
        by_unit, x=COL_TOTAL, y=COL_UNIT, orientation="h", text_auto=",.0f",
        color_discrete_sequence=["#2a6f97"],
    )
    fig2.update_layout(yaxis_title=None, xaxis_title="กิโลกรัม", height=max(400, top_n * 32))
    st.plotly_chart(fig2, width="stretch")

# ---------------------------------------------------------------------------
# กราฟ 3 & 4
# ---------------------------------------------------------------------------
c3, c4 = st.columns(2)

with c3:
    st.subheader("🥧 กราฟ 3: สัดส่วนขยะแยกตามสังกัด")
    by_group = filtered.groupby(COL_GROUP, as_index=False)[COL_TOTAL].sum()
    fig3 = px.pie(by_group, names=COL_GROUP, values=COL_TOTAL, hole=0.45,
                  color_discrete_sequence=px.colors.qualitative.Set2)
    fig3.update_traces(textposition="inside", textinfo="percent+label")
    fig3.update_layout(showlegend=False)
    st.plotly_chart(fig3, width="stretch")

with c4:
    st.subheader("👥 กราฟ 4: จำนวนคน vs ปริมาณขยะ (รายหน่วยงาน)")
    per_unit = filtered.groupby([COL_UNIT, COL_GROUP], as_index=False).agg(
        คนเฉลี่ย=(COL_PEOPLE, "mean"),
        ขยะรวม=(COL_TOTAL, "sum"),
        ใช้ประโยชน์=(COL_REUSE, "sum"),
    )
    per_unit["ร้อยละใช้ประโยชน์"] = (
        per_unit["ใช้ประโยชน์"] / per_unit["ขยะรวม"].where(per_unit["ขยะรวม"] > 0) * 100
    ).round(1)
    fig4 = px.scatter(
        per_unit, x="คนเฉลี่ย", y="ขยะรวม", color=COL_GROUP, size="ขยะรวม", size_max=40,
        hover_name=COL_UNIT, hover_data={"ร้อยละใช้ประโยชน์": True},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig4.update_layout(xaxis_title="จำนวนคนเฉลี่ย", yaxis_title="ขยะที่เกิดขึ้นรวม (กก.)",
                       legend=dict(orientation="h", y=-0.25), legend_title=None)
    st.plotly_chart(fig4, width="stretch")

# ---------------------------------------------------------------------------
# ตารางข้อมูล
# ---------------------------------------------------------------------------
with st.expander("📋 ดูตารางข้อมูลที่กรองแล้ว"):
    st.dataframe(filtered.drop(columns=["month_no"]), width="stretch", hide_index=True)
    st.download_button(
        "⬇️ ดาวน์โหลด CSV",
        filtered.drop(columns=["month_no"]).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"waste_{year}_filtered.csv",
        mime="text/csv",
    )
