"""臺北 YouBike 空站觀察：115-1 地理資訊系統運用程式的 App 範本。

執行方式：在終端機輸入 solara run app.py
"""

from pathlib import Path

import leafmap.leafmap as leafmap
import pandas as pd
import plotly.express as px
import solara

DATA_PATH = Path(__file__).parent / "data" / "w3_youbike_long3.csv"

# 讀檔放在元件外面：App 啟動時只讀一次，切換選項時不會重新讀檔。
# sno、act 指定為字串，避免被自動轉成整數（W3 的 read_json 陷阱，read_csv 也一樣）。
df = pd.read_csv(DATA_PATH, dtype={"sno": str, "act": str})
print("[效能測試]正在載入csv檔") #檢驗csv是否重複讀檔
df = df[df["act"] == "1"]  # 只看營運中的站

時段們 = sorted(df["時段"].unique())
行政區們 = ["全部行政區"] + sorted(df["sarea"].unique())

# reactive：值改變時，用到它的元件會自動重新執行。
門檻 = solara.reactive(0)
時段 = solara.reactive(時段們[0])
行政區 = solara.reactive("全部行政區")


def 各區空站比例(資料, 門檻值):
    """計算各區的站數、空站數與空站比例（可借車 <= 門檻值 算空站）。"""
    資料 = 資料.assign(空站=資料["available_rent_bikes"] <= 門檻值)
    表 = 資料.groupby("sarea").agg(站數=("sno", "size"), 空站數=("空站", "sum")) 
    表["空站比例"] = (表["空站數"] / 表["站數"]).round(3)
    return 表.sort_values("空站比例", ascending=False).reset_index()


def 各時段可借車總數(資料):
    """計算各時段的可借車總數。"""
    表 = 資料.groupby("時段").agg(可借車總數=("available_rent_bikes", "sum")).reset_index()
    表["時段"] = pd.Categorical(表["時段"], categories=時段們, ordered=True)
    return 表.sort_values("時段")


def 建立站點地圖(資料, 行政區名稱):
    """用 Leafmap 在地圖上顯示目前篩選到的站點。"""
    有座標資料 = 資料.dropna(subset=["latitude", "longitude"])
    if 有座標資料.empty:
        return None

    中心緯度 = float(有座標資料["latitude"].mean())
    中心經度 = float(有座標資料["longitude"].mean())
    地圖 = leafmap.Map(
        center=(中心緯度, 中心經度),
        zoom=14 if 行政區名稱 != "全部行政區" else 12,
        height="400px",
        scroll_wheel_zoom=True,
        draw_control=False,
        measure_control=False,
    )

    特徵們 = []
    for 站 in 有座標資料.itertuples():
        特徵們.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(站.longitude), float(站.latitude)],
                },
                "properties": {"站名": str(站.sna)},
            }
        )

    地圖.add_geojson(
        {"type": "FeatureCollection", "features": 特徵們},
        layer_name="YouBike 站點",
        point_style={
            "radius": 6,
            "color": "#ffffff",
            "weight": 1,
            "fillColor": "#2878B5",
            "fillOpacity": 0.85,
        },
        info_mode=None,
        zoom_to_layer=False,
    )
    return 地圖


@solara.component
def Page():
    solara.Title("YouBike 空站觀察")
    solara.Markdown("# 臺北 YouBike 各區空站比例")

    # 滑桿預設會撐滿整個頁寬，用 Column 限制最大寬度，比較好操作。
    with solara.Column(style={"max-width": "480px"}):
        solara.SliderInt("空站門檻：可借車 ≤", value=門檻, min=0, max=5)
        solara.Select("選擇行政區", value=行政區, values=行政區們)
    solara.ToggleButtonsSingle(value=時段, values=時段們)

    當時 = df[df["時段"] == 時段.value]
    if 行政區.value != "全部行政區":
        當時 = 當時[當時["sarea"] == 行政區.value]

    solara.Markdown("## YouBike 站點地圖")
    地圖 = 建立站點地圖(當時, 行政區.value)
    if 地圖 is None:
        solara.Warning("目前篩選條件沒有可顯示的站點。")
    else:
        # isolation 避免地圖控制項的圖層順序蓋住頁面其他內容。
        with solara.Div(style={"width": "100%", "isolation": "isolate"}):
            solara.display(地圖)

    表 = 各區空站比例(當時, 門檻.value)

    if 行政區.value == "全部行政區":
        圖表標題 = f"{時段.value}，可借車 ≤ {門檻.value} 算空站（只算營運中的站）"
    else:
        圖表標題 = f"{行政區.value}，{時段.value}，可借車 ≤ {門檻.value} 算空站（只算營運中的站）"

    圖 = px.bar(
        表,
        x="空站比例",
        y="sarea",
        orientation="h",
        title=圖表標題,
        labels={"sarea": "", "空站比例": "空站比例"},
    )
    # 每區給 30 px 高度，行政區名稱才不會被 Plotly 自動隔行省略；換成區數更多的縣市也適用。
    圖.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_tickformat=".0%",
        height=150 + 30 * len(表),
    )
    solara.FigurePlotly(圖)

    solara.DataFrame(表)

    各時段資料 = df
    if 行政區.value != "全部行政區":
        各時段資料 = 各時段資料[各時段資料["sarea"] == 行政區.value]

    可借車表 = 各時段可借車總數(各時段資料)

    if 行政區.value == "全部行政區":
        可借車圖標題 = "全部行政區各時段可借車總數（只算營運中的站）"
    else:
        可借車圖標題 = f"{行政區.value}各時段可借車總數（只算營運中的站）"

    可借車圖 = px.bar(
        可借車表,
        x="時段",
        y="可借車總數",
        title=可借車圖標題,
        labels={"時段": "時段", "可借車總數": "可借車總數"},
    )
    可借車圖.update_layout(height=420)

    solara.Markdown("## 臺北Youbike各時段可借車總數")
    solara.FigurePlotly(可借車圖)
    solara.DataFrame(可借車表)

    solara.Markdown(
        "資料來源：[臺北市 YouBike 2.0 即時資料（臺北市資料大平臺）]"
        "(https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json)，"
        "依政府資料開放授權條款第 1 版使用。"
        f"資料時間：{時段.value}。"
        "\n\n底圖來源：OpenStreetMap contributors，"
        "[底圖著作權與使用說明](https://www.openstreetmap.org/copyright)。"
    )
