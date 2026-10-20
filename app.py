"""臺北 YouBike 空站觀察：115-1 地理資訊系統運用程式的 App 範本。

執行方式：在終端機輸入 solara run app.py
"""

from pathlib import Path

from ipyleaflet import TileLayer
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

# 依可借車數分五級，使用適合色覺辨識的 Cividis 順序色帶。
分級顏色 = {
    "0 輛（空站）": "#00204C",
    "1–2 輛": "#575D6D",
    "3–5 輛": "#8C8981",
    "6–10 輛": "#C8B978",
    "11 輛以上": "#FFEA46",
}


def 各區空站比例(資料, 門檻值):
    """計算各區的站數、空站數與空站比例（可借車 <= 門檻值 算空站）。"""
    資料 = 資料.assign(空站=資料["available_rent_bikes"] <= 門檻值)
    表 = 資料.groupby("sarea").agg(站數=("sno", "size"), 空站數=("空站", "sum")) 
    表["空站比例"] = (表["空站數"] / 表["站數"]).round(3)
    return 表.sort_values("空站比例", ascending=False).reset_index()


def 可借車分級(可借車數):
    """依站點可借車數回傳分級名稱。"""
    if 可借車數 == 0:
        return "0 輛（空站）"
    if 可借車數 <= 2:
        return "1–2 輛"
    if 可借車數 <= 5:
        return "3–5 輛"
    if 可借車數 <= 10:
        return "6–10 輛"
    return "11 輛以上"


def 各級距站數(資料):
    """計算目前篩選資料中，各可借車級距的站數。"""
    表 = 資料.copy()
    表["可借車級距"] = 表["available_rent_bikes"].map(可借車分級)
    表 = 表["可借車級距"].value_counts().reindex(分級顏色, fill_value=0)
    return 表.rename_axis("可借車級距").rename("站數").reset_index()


def 建立站點地圖(資料, 行政區名稱):
    """用 Leafmap 顯示分級站點，並明確加入 OpenStreetMap 底圖。"""
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

    # 移除 Leafmap 預設圖層，再明確加入底圖，避免部署時依賴隱含預設值。
    地圖.layers = ()
    地圖.add_layer(
        TileLayer(
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution="© OpenStreetMap contributors",
            name="OpenStreetMap",
        )
    )

    站點特徵 = []
    for 站 in 有座標資料.itertuples():
        可借車數 = int(站.available_rent_bikes)
        級距 = 可借車分級(可借車數)
        站點特徵.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(站.longitude), float(站.latitude)],
                },
                "properties": {
                    "站名": str(站.sna),
                    "可借車數": 可借車數,
                    "可借車級距": 級距,
                },
            }
        )

    def 站點樣式(特徵):
        """依每個站點的可借車級距設定圓點顏色。"""
        級距 = 特徵["properties"]["可借車級距"]
        return {
            "radius": 6,
            "color": "#ffffff",
            "weight": 1,
            "fillColor": 分級顏色[級距],
            "fillOpacity": 0.9,
        }

    地圖.add_geojson(
        {"type": "FeatureCollection", "features": 站點特徵},
        layer_name="YouBike 站點",
        style_callback=站點樣式,
        point_style={"radius": 6},
        info_mode="on_click",
        fields=["站名", "可借車數"],
        zoom_to_layer=False,
    )

    地圖.add_legend(
        title="可借車數（輛）",
        legend_dict=分級顏色,
        position="bottomright",
        shape_type="circle",
    )
    return 地圖


@solara.component
def Page():
    solara.Title("YouBike 空站觀察")
    solara.Markdown("# 臺北 YouBike 各區空站比例")
    solara.Markdown(
        "### 資料與地圖來源\n"
        "- 資料來源：[臺北市 YouBike 2.0 即時資料（臺北市資料大平臺）]"
        "(https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json)，"
        "依政府資料開放授權條款第 1 版使用。\n"
        f"- 資料時段：{時段.value}（目前選取時段）。\n"
        "- 底圖來源：OpenStreetMap contributors；"
        "[底圖著作權與使用說明](https://www.openstreetmap.org/copyright)。"
    )

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

    級距站數表 = 各級距站數(當時)
    if 行政區.value == "全部行政區":
        級距圖標題 = f"{時段.value} 各可借車級距站數"
    else:
        級距圖標題 = f"{行政區.value}・{時段.value} 各可借車級距站數"

    級距圖 = px.bar(
        級距站數表,
        x="可借車級距",
        y="站數",
        title=級距圖標題,
        color="可借車級距",
        color_discrete_map=分級顏色,
        category_orders={"可借車級距": list(分級顏色)},
        labels={"可借車級距": "可借車數（輛）", "站數": "站數"},
    )
    級距圖.update_layout(height=340, showlegend=False)

    solara.Markdown("## 目前篩選站點的可借車級距")
    solara.FigurePlotly(級距圖)
    solara.DataFrame(級距站數表)

