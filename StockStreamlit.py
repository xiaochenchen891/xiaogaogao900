import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time as dtime
import requests
import os

# 清除代理（避免某些环境下请求失败）
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

st.set_page_config(
    page_title="A股量价分析",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="collapsed",
)

# ====================== 是否交易时段 ======================
def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (dtime(9, 25) <= t <= dtime(11, 32)) or (dtime(13, 0) <= t <= dtime(15, 2))

# ====================== CSS ======================
st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {
        padding: 0.4rem 0.9rem 0.3rem 0.9rem !important;
        max-width: 100% !important;
    }
    html, body, [class*="css"] {font-size: 14px !important;}

    .top-bar {
        display:flex; justify-content:space-between; align-items:center;
        padding:4px 10px; margin-bottom:6px;
        background:linear-gradient(90deg,#f8f9fa,#fff);
        border-left:4px solid #1976d2; border-radius:6px;
        font-size:0.85rem;
    }
    .top-title {font-size:1rem; font-weight:700; color:#1976d2;}

    .stock-header {
        display:flex; justify-content:space-between; align-items:center;
        flex-wrap:wrap; gap:6px; padding:4px 4px 4px 4px;
        background:#fff; border:1px solid #eee; border-radius:6px;
        margin-bottom:2px;
    }
    .stock-name {font-size:1rem; font-weight:700; color:#333;}
    .badges {display:flex; gap:5px; flex-wrap:wrap;}
    .badge {
        display:inline-flex; align-items:center; gap:5px;
        padding:2px 9px; border-radius:12px; font-size:0.78rem; font-weight:600;
    }
    .badge::before {
        content:""; width:7px; height:7px; border-radius:50%; display:inline-block;
    }
    .badge-sup {background:#e8f5e9; color:#1b5e20;}
    .badge-sup::before {background:#43a047;}
    .badge-add {background:#e0f7fa; color:#006064;}
    .badge-add::before {background:#00bcd4;}
    .badge-stop {background:#fff3e0; color:#e65100;}
    .badge-stop::before {background:#ff9800;}
    .badge-res {background:#ffebee; color:#b71c1c;}
    .badge-res::before {background:#e53935;}

    .legend-row {
        display:flex; gap:14px; padding:2px 4px; font-size:0.72rem;
        color:#777; flex-wrap:wrap; justify-content:center;
    }
    .legend-row span::before {
        content:""; display:inline-block; width:9px; height:9px;
        border-radius:50%; margin-right:4px; vertical-align:middle;
    }
    .lg-green::before  {background:#a5d6a7;}
    .lg-blue::before   {background:#80deea;}
    .lg-red::before    {background:#ef9a9a;}
    .lg-orange::before {background:#ffcc80;}

    [data-testid="stVerticalBlock"] {gap: 0.35rem !important;}
    [data-testid="stHorizontalBlock"] {gap: 0.5rem !important;}
</style>
""", unsafe_allow_html=True)

# ====================== 标的 ======================
TARGETS = {
    "信维通信":   {"code": "300136", "market": "sz"},
    "机器人ETF":  {"code": "562500", "market": "sh"},
    "仕佳光子":   {"code": "688313", "market": "sh"},
    "赣锋锂业":   {"code": "002460", "market": "sz"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

# ====================== 数据源 ======================
def fetch_sina(code, market, days):
    symbol = f"{market}{code}"
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
           f"?symbol={symbol}&scale=240&ma=no&datalen={days}")
    r = requests.get(url, headers=HEADERS, timeout=8)
    data = r.json()
    if not data:
        raise ValueError("空数据")
    df = pd.DataFrame(data).rename(columns={"day": "date"})
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "close", "high", "low", "volume"]] \
        .sort_values("date").reset_index(drop=True)


def fetch_tencent(code, market, days):
    symbol = f"{market}{code}"
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={symbol},day,,,{days},qfq")
    r = requests.get(url, headers=HEADERS, timeout=8)
    js = r.json()
    data = js.get("data", {}).get(symbol, {})
    klines = data.get("qfqday") or data.get("day")
    if not klines:
        raise ValueError("空数据")
    df = pd.DataFrame(klines).iloc[:, :6]
    df.columns = ["date", "open", "close", "high", "low", "volume"]
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


# 交易时段：30 秒缓存（按时间戳分桶）
@st.cache_data(ttl=30, show_spinner=False)
def fetch_data_live(code, market, days, _stamp):
    for fn in (fetch_sina, fetch_tencent):
        try:
            df = fn(code, market, days)
            if df is not None and len(df) > 30:
                return df
        except Exception:
            continue
    return None


# 非交易时段：5 分钟缓存
@st.cache_data(ttl=300, show_spinner=False)
def fetch_data_cached(code, market, days):
    for fn in (fetch_sina, fetch_tencent):
        try:
            df = fn(code, market, days)
            if df is not None and len(df) > 30:
                return df
        except Exception:
            continue
    return None


def fetch_data(code, market, days=160):
    if is_market_open():
        stamp = int(datetime.now().timestamp() // 30)
        return fetch_data_live(code, market, days, stamp)
    return fetch_data_cached(code, market, days)


# ====================== 指标 ======================
def compute_indicators(df):
    df = df.copy()
    df["MA5"]  = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()
    df["MA20"] = df["close"].rolling(20).mean()
    return df


# ====================== 量价综合：支撑/压力 ======================
def find_levels_vp(df_full, bins=30):
    """
    多窗口（20/60/120日）量价加权融合 → 综合支撑 / 压力
    """
    close = float(df_full["close"].iloc[-1])
    n = len(df_full)
    raw = [(min(20, n), 0.25), (min(60, n), 0.45), (min(120, n), 0.30)]
    windows = [(w, wt) for w, wt in raw if w >= 10]
    if not windows:
        windows = [(n, 1.0)]

    max_w = max(w for w, _ in windows)
    full_recent = df_full.tail(max_w)
    p_min = float(full_recent["low"].min())
    p_max = float(full_recent["high"].max())
    if p_max <= p_min:
        p_max = p_min * 1.01 + 1e-6
    edges = np.linspace(p_min, p_max, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2

    comb_sup = np.zeros(bins)
    comb_res = np.zeros(bins)
    comb_vol = np.zeros(bins)
    weight_sum = sum(wt for _, wt in windows)
    decay = 0.985

    for window, wt in windows:
        norm_wt = wt / weight_sum
        recent = df_full.tail(window).reset_index(drop=True)
        m = len(recent)

        tv = np.zeros(bins)   # 总成交量
        uv = np.zeros(bins)   # 上涨日量
        dv = np.zeros(bins)   # 下跌日量
        st_ = np.zeros(bins)  # 触及支撑次数
        rt_ = np.zeros(bins)  # 触及压力次数
        sr  = np.zeros(bins)  # 反弹确认
        rr  = np.zeros(bins)  # 回落确认

        avg_range = (recent["high"] - recent["low"]).replace(0, np.nan).mean()
        if pd.isna(avg_range) or avg_range <= 0:
            avg_range = recent["close"].iloc[-1] * 0.02
        tol = avg_range * 0.45

        for i, row in recent.iterrows():
            lo, hi = float(row["low"]), float(row["high"])
            o, c = float(row["open"]), float(row["close"])
            v = float(row["volume"])
            if hi <= lo or v <= 0:
                continue
            rec_w = decay ** (m - 1 - i)
            touched = np.where((centers >= lo) & (centers <= hi))[0]
            if len(touched) == 0:
                idx = np.clip(np.digitize((hi + lo + c) / 3, edges) - 1, 0, bins - 1)
                touched = np.array([idx])
            wv = v * rec_w / len(touched)
            for idx in touched:
                tv[idx] += wv
                if c >= o:
                    uv[idx] += wv
                else:
                    dv[idx] += wv
            for j, p in enumerate(centers):
                if abs(lo - p) <= tol:
                    st_[j] += 1
                    if c > p and c >= o:
                        sr[j] += 1
                if abs(hi - p) <= tol:
                    rt_[j] += 1
                    if c < p and c <= o:
                        rr[j] += 1

        def nm(a):
            mx = np.nanmax(a)
            return a / mx if mx > 0 else np.zeros_like(a)

        vol_s = nm(tv)
        sup_s = 0.40 * vol_s + 0.25 * nm(st_) + 0.20 * nm(sr) + 0.15 * (uv / np.maximum(tv, 1e-9))
        res_s = 0.40 * vol_s + 0.25 * nm(rt_) + 0.20 * nm(rr) + 0.15 * (dv / np.maximum(tv, 1e-9))
        comb_sup += sup_s * norm_wt
        comb_res += res_s * norm_wt
        if tv.max() > 0:
            comb_vol += (tv / tv.max()) * norm_wt

    # 距离惩罚（远离当前价的位失效）
    dist = np.abs(centers - close) / max(close, 1e-9)
    penalty = np.exp(-dist * 8)
    fs = comb_sup * penalty
    fr = comb_res * penalty
    below = centers < close
    above = centers > close

    def pick(mask, scores):
        cands = sorted(
            [(float(centers[i]), float(scores[i])) for i in range(bins)
             if mask[i] and comb_vol[i] > 1e-9],
            key=lambda x: x[1], reverse=True
        )
        return cands[0][0] if cands else None

    sup = pick(below, fs)
    res = pick(above, fr)
    if sup is None:
        sup = close * 0.97
    if res is None:
        res = close * 1.03

    stop     = sup * 0.98
    add_low  = sup * 0.992
    add_high = sup * 1.012

    return {
        "支撑":   round(sup, 2),
        "止损":   round(stop, 2),
        "压力":   round(res, 2),
        "补仓低": round(add_low, 2),
        "补仓高": round(add_high, 2),
    }


# ====================== 单图绘制 ======================
def plot_card_chart(df_show, levels, height=300):
    df = df_show.copy().reset_index(drop=True)
    df["x"] = df["date"].dt.strftime("%m/%d")

    close_now = df["close"].iloc[-1]
    sup, res, stop = levels["支撑"], levels["压力"], levels["止损"]
    al, ah = levels["补仓低"], levels["补仓高"]

    y_min = min(df["low"].min(), stop) * 0.98
    y_max = max(df["high"].max(), res) * 1.02

    fig = go.Figure()

    # 4 个色带
    fig.add_hrect(y0=res,   y1=y_max, fillcolor="rgba(255,152,0,0.10)", line_width=0, layer="below")
    fig.add_hrect(y0=stop,  y1=sup,   fillcolor="rgba(76,175,80,0.10)", line_width=0, layer="below")
    fig.add_hrect(y0=y_min, y1=stop,  fillcolor="rgba(244,67,54,0.10)", line_width=0, layer="below")
    fig.add_hrect(y0=al,    y1=ah,    fillcolor="rgba(0,188,212,0.22)", line_width=0, layer="below")

    # 三条参考线
    fig.add_hline(y=res,  line_dash="dash",    line_color="#e53935", line_width=1.5,
                  annotation_text=f"<b>压力 {res:.2f}</b>", annotation_position="top right",
                  annotation_font=dict(size=10, color="#e53935"))
    fig.add_hline(y=sup,  line_dash="dash",    line_color="#43a047", line_width=1.5,
                  annotation_text=f"<b>支撑 {sup:.2f}</b>", annotation_position="bottom right",
                  annotation_font=dict(size=10, color="#43a047"))
    fig.add_hline(y=stop, line_dash="dashdot", line_color="#ff9800", line_width=1.3,
                  annotation_text=f"<b>止损 {stop:.2f}</b>", annotation_position="bottom right",
                  annotation_font=dict(size=10, color="#ff9800"))

    # 收盘价折线
    fig.add_trace(go.Scatter(
        x=df["x"], y=df["close"],
        mode="lines+markers",
        name=f"收盘价 (现价 {close_now:.2f})",
        line=dict(color="#1e88e5", width=2.6, shape="spline"),
        marker=dict(size=7, color="#1e88e5"),
    ))
    if df["MA5"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["x"], y=df["MA5"], mode="lines", name="MA5",
            line=dict(color="#ab47bc", width=1.2, dash="dash")
        ))
    if df["MA10"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["x"], y=df["MA10"], mode="lines", name="MA10",
            line=dict(color="#26c6da", width=1.2, dash="dash")
        ))

    # 现价标注
    fig.add_annotation(
        x=df["x"].iloc[-1], y=close_now,
        text=f"<b>现价 {close_now:.2f}</b>",
        showarrow=False, xshift=-8, yshift=14,
        font=dict(size=10, color="#1e88e5"),
    )

    fig.update_layout(
        height=height,
        margin=dict(l=8, r=18, t=10, b=28),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        legend=dict(orientation="h", y=-0.14, x=0.5, xanchor="center",
                    font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
        font=dict(size=10),
        yaxis=dict(range=[y_min, y_max], showgrid=True, gridcolor="#f0f0f0"),
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
        hovermode="x unified",
    )
    return fig


# ====================== 渲染单卡片 ======================
def render_card(name, df_show, levels, height):
    sup, res, stop = levels["支撑"], levels["压力"], levels["止损"]
    al, ah = levels["补仓低"], levels["补仓高"]

    st.markdown(f"""
    <div class="stock-header">
        <div class="stock-name">{name}</div>
        <div class="badges">
            <span class="badge badge-sup">支撑 {sup:.2f}</span>
            <span class="badge badge-add">适合补仓 {al:.2f}-{ah:.2f}</span>
            <span class="badge badge-stop">止损 {stop:.2f}</span>
            <span class="badge badge-res">压力 {res:.2f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.plotly_chart(
        plot_card_chart(df_show, levels, height=height),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.markdown("""
    <div class="legend-row">
        <span class="lg-green">绿色区: 支撑-止损之间</span>
        <span class="lg-blue">蓝色区: 适合补仓</span>
        <span class="lg-red">红色区: 跌破止损</span>
        <span class="lg-orange">橙色区: 突破压力</span>
    </div>
    """, unsafe_allow_html=True)


# ====================== 侧边栏 ======================
with st.sidebar:
    st.markdown("## ⚙️ 设置")
    show_days   = st.slider("显示天数", 5, 30, 7, 1)
    chart_h     = st.slider("单图高度", 220, 420, 300, 10)
    bins        = st.slider("价格分箱", 20, 60, 30, 5)
    auto_refresh = st.checkbox("交易时段自动刷新（30s）", value=True)
    if st.button("🔄 强制刷新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"刷新: {datetime.now().strftime('%H:%M:%S')}")
    if is_market_open():
        st.success("📡 交易中")
    else:
        st.info("💤 休市中")


# ====================== 顶部状态栏 ======================
status_text = "🟢 交易中（数据每 30 秒自动更新）" if is_market_open() else "🔴 休市（显示最新收盘）"
st.markdown(f"""
<div class="top-bar">
    <span class="top-title">📈 A股技术分析助手 · 量价分析</span>
    <span>{status_text} · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
</div>
""", unsafe_allow_html=True)


# ====================== 2 × 2 网格 ======================
items = list(TARGETS.items())
for row in range(2):
    cols = st.columns(2, gap="small")
    for c in range(2):
        idx = row * 2 + c
        if idx >= len(items):
            break
        name, info = items[idx]
        with cols[c]:
            df_full = fetch_data(info["code"], info["market"], 160)
            if df_full is None or len(df_full) < 30:
                st.error(f"❌ {name} 数据加载失败")
                continue
            df_full = compute_indicators(df_full)
            df_show = df_full.tail(show_days).reset_index(drop=True)
            levels  = find_levels_vp(df_full, bins=bins)
            render_card(name, df_show, levels, chart_h)


# ====================== 自动刷新（不阻塞 UI） ======================
if auto_refresh and is_market_open():
    st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)