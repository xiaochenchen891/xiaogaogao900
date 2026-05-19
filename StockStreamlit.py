import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
import os

for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

st.set_page_config(page_title="A股技术分析助手", layout="wide", page_icon="📈",
                   initial_sidebar_state="collapsed")

# ========== 全局CSS（紧凑型） ==========
st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {padding: 0.6rem 1.2rem 0.5rem 1.2rem !important; max-width: 100% !important;}
    
    html, body, [class*="css"] {font-size: 15px !important;}
    h1 {font-size: 1.4rem !important; margin: 0 !important; padding: 0 !important;}
    h3 {font-size: 1.05rem !important; margin: 0.3rem 0 0.2rem 0 !important; padding: 0 !important;}
    h4 {font-size: 0.95rem !important; margin: 0.2rem 0 !important;}
    
    .header-row {display: flex; align-items: center; gap: 14px; margin-bottom: 4px;}
    
    .stTabs [data-baseweb="tab-list"] {gap: 4px; border-bottom: 2px solid #e0e0e0; margin-bottom: 6px;}
    .stTabs [data-baseweb="tab"] {
        font-size: 0.95rem !important; font-weight: 600 !important;
        padding: 6px 16px !important; background: #f5f5f5;
        border-radius: 6px 6px 0 0; min-height: auto !important;
    }
    .stTabs [aria-selected="true"] {background: #1976d2 !important; color: #fff !important;}
    
    [data-testid="stMetric"] {
        background: #fff; padding: 8px 12px; border-radius: 8px;
        border-left: 4px solid #1976d2;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    [data-testid="stMetricValue"] {font-size: 1.35rem !important; font-weight: 700 !important;}
    [data-testid="stMetricLabel"] {font-size: 0.78rem !important; color: #666 !important;}
    [data-testid="stMetricDelta"] {font-size: 0.8rem !important;}
    [data-testid="stMetric"] > div {gap: 2px !important;}
    
    .info-bar {
        background: linear-gradient(90deg, #f8f9fa 0%, #fff 100%);
        padding: 6px 14px; border-radius: 8px; margin-bottom: 6px;
        border-left: 4px solid #1976d2;
        display: flex; justify-content: space-between; align-items: center;
        font-size: 0.9rem;
    }
    .trend-badge {
        display: inline-block; padding: 3px 12px; border-radius: 12px;
        font-size: 0.9rem; font-weight: 700;
    }
    .trend-bull {background: #c8e6c9; color: #1b5e20;}
    .trend-bear {background: #ffcdd2; color: #b71c1c;}
    .trend-side {background: #fff9c4; color: #f57f17;}
    
    .signal-card {
        padding: 7px 11px; border-radius: 6px; margin-bottom: 5px;
        font-size: 0.85rem; line-height: 1.4; border-left: 4px solid;
    }
    .signal-card b {font-size: 0.92rem;}
    .signal-success {background: #e8f5e9; border-color: #2e7d32; color: #1b5e20;}
    .signal-warning {background: #fff8e1; border-color: #f57c00; color: #e65100;}
    .signal-error   {background: #ffebee; border-color: #c62828; color: #b71c1c;}
    .signal-info    {background: #e3f2fd; border-color: #1565c0; color: #0d47a1;}
    
    .level-table {
        width: 100%; font-size: 0.85rem; border-collapse: collapse;
        background: #fff; border-radius: 6px; overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .level-table th {
        background: #f5f5f5; padding: 5px 10px; text-align: left;
        font-weight: 600; font-size: 0.8rem; color: #555;
    }
    .level-table td {padding: 5px 10px; border-top: 1px solid #f0f0f0;}
    .level-table tr td:first-child {font-weight: 600;}
    .level-sup {color: #2e7d32;}
    .level-res {color: #c62828;}
    
    [data-testid="stVerticalBlock"] {gap: 0.4rem !important;}
    [data-testid="stHorizontalBlock"] {gap: 0.5rem !important;}
    
    .stCaption {font-size: 0.75rem !important; color: #999 !important;}
</style>
""", unsafe_allow_html=True)

# ========== 标的 ==========
TARGETS = {
    "赣锋锂业 (002460)": {"code": "002460", "market": "sz"},
    "仕佳光子 (688313)": {"code": "688313", "market": "sh"},
    "信维通信 (300136)": {"code": "300136", "market": "sz"},
    "机器人ETF (562500)": {"code": "562500", "market": "sh"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

# ========== 数据源 ==========
def fetch_sina(code, market, days):
    symbol = f"{market}{code}"
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
           f"?symbol={symbol}&scale=240&ma=no&datalen={days}")
    r = requests.get(url, headers=HEADERS, timeout=8)
    data = r.json()
    if not data: raise ValueError("空数据")
    df = pd.DataFrame(data).rename(columns={"day": "date"})
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "close", "high", "low", "volume"]].sort_values("date").reset_index(drop=True)

def fetch_tencent(code, market, days):
    symbol = f"{market}{code}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq"
    r = requests.get(url, headers=HEADERS, timeout=8)
    js = r.json()
    data = js.get("data", {}).get(symbol, {})
    klines = data.get("qfqday") or data.get("day")
    if not klines: raise ValueError("空数据")
    df = pd.DataFrame(klines).iloc[:, :6]
    df.columns = ["date", "open", "close", "high", "low", "volume"]
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(code, market, fetch_days=160):
    sources = [("新浪财经", lambda: fetch_sina(code, market, fetch_days)),
               ("腾讯财经", lambda: fetch_tencent(code, market, fetch_days))]
    errors = []
    for name, fn in sources:
        try:
            df = fn()
            if df is not None and len(df) > 30:
                return df, name, errors
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__} - {str(e)[:80]}")
    return None, None, errors

# ========== 指标 ==========
def compute_indicators(df):
    df = df.copy()
    df["MA5"]  = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()
    df["MA20"] = df["close"].rolling(20).mean()
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

# ========== 量价支撑压力（多时间框架综合版） ==========
def build_volume_profile(df_full, lookback=60, bins=30, decay=0.985, edges=None):
    """
    基于量价关系构建 Volume Profile。
    - 每日成交量按 high-low 区间分摊到经过的价格档
    - 越新的交易日权重越高（指数衰减）
    - 同时统计上涨/下跌成交量
    - 支持外部传入 edges，便于多窗口在同一价格分箱下融合
    """
    recent = df_full.tail(lookback).copy().reset_index(drop=True)

    if edges is None:
        price_min = float(recent["low"].min())
        price_max = float(recent["high"].max())
        if price_max <= price_min:
            price_max = price_min * 1.01 + 1e-6
        edges = np.linspace(price_min, price_max, bins + 1)
    else:
        bins = len(edges) - 1

    centers = (edges[:-1] + edges[1:]) / 2

    total_vol = np.zeros(bins)
    up_vol = np.zeros(bins)
    down_vol = np.zeros(bins)

    n = len(recent)
    for i, row in recent.iterrows():
        low = float(row["low"]); high = float(row["high"])
        open_ = float(row["open"]); close = float(row["close"])
        volume = float(row["volume"])
        if high <= low or volume <= 0:
            continue

        recency_weight = decay ** (n - 1 - i)

        touched = np.where((centers >= low) & (centers <= high))[0]
        if len(touched) == 0:
            tp = (high + low + close) / 3
            idx = np.clip(np.digitize(tp, edges) - 1, 0, bins - 1)
            touched = np.array([idx])

        weighted_volume = volume * recency_weight / len(touched)
        for idx in touched:
            total_vol[idx] += weighted_volume
            if close >= open_:
                up_vol[idx] += weighted_volume
            else:
                down_vol[idx] += weighted_volume

    return centers, total_vol, up_vol, down_vol, edges


def score_price_levels(df_full, centers, total_vol, up_vol, down_vol, lookback=60):
    """
    对每个价格档进行量价综合评分。
    支撑评分: 成交量密集 + 低点触达 + 反弹收涨 + 上涨成交量占比
    压力评分: 成交量密集 + 高点触达 + 回落收跌 + 下跌成交量占比
    """
    recent = df_full.tail(lookback).copy().reset_index(drop=True)
    bins = len(centers)

    support_touch = np.zeros(bins)
    resistance_touch = np.zeros(bins)
    support_rebound = np.zeros(bins)
    resistance_reject = np.zeros(bins)

    avg_range = (recent["high"] - recent["low"]).replace(0, np.nan).mean()
    if pd.isna(avg_range) or avg_range <= 0:
        avg_range = recent["close"].iloc[-1] * 0.02
    tolerance = avg_range * 0.45

    for _, row in recent.iterrows():
        low = float(row["low"]); high = float(row["high"])
        open_ = float(row["open"]); close = float(row["close"])

        for i, price in enumerate(centers):
            if abs(low - price) <= tolerance:
                support_touch[i] += 1
                if close > price and close >= open_:
                    support_rebound[i] += 1
            if abs(high - price) <= tolerance:
                resistance_touch[i] += 1
                if close < price and close <= open_:
                    resistance_reject[i] += 1

    def normalize(arr):
        arr = np.asarray(arr, dtype=float)
        max_v = np.nanmax(arr) if len(arr) else 0
        if max_v <= 0 or np.isnan(max_v):
            return np.zeros_like(arr)
        return arr / max_v

    vol_score = normalize(total_vol)
    sup_touch_score = normalize(support_touch)
    res_touch_score = normalize(resistance_touch)
    rebound_score = normalize(support_rebound)
    reject_score = normalize(resistance_reject)

    up_ratio = up_vol / np.maximum(total_vol, 1e-9)
    down_ratio = down_vol / np.maximum(total_vol, 1e-9)

    support_score = (
        0.40 * vol_score +
        0.25 * sup_touch_score +
        0.20 * rebound_score +
        0.15 * up_ratio
    )
    resistance_score = (
        0.40 * vol_score +
        0.25 * res_touch_score +
        0.20 * reject_score +
        0.15 * down_ratio
    )
    return support_score, resistance_score


def find_levels(df_full, df_show, mid_lookback=60, bins=30):
    """
    多时间框架综合支撑压力位（与显示天数完全解耦）：
      - 短期窗口  20日（权重 0.25）：捕捉近期活跃成交区
      - 中期窗口 mid_lookback 日（权重 0.45）：主要量价结构（用户可调）
      - 长期窗口 120日（权重 0.30）：重要历史关口
    三个窗口在统一的价格分箱下独立评分，再加权融合，最后做距离惩罚选位。
    """
    close = float(df_show["close"].iloc[-1])
    n_full = len(df_full)

    # 三个窗口 + 权重，自适应数据长度
    raw_windows = [
        (min(20, n_full), 0.25),
        (min(mid_lookback, n_full), 0.45),
        (min(120, n_full), 0.30),
    ]
    # 合并相同窗口长度的权重，去除过短窗口
    merged = {}
    for w, wt in raw_windows:
        if w < 10:
            continue
        merged[w] = merged.get(w, 0.0) + wt
    windows = sorted(merged.items(), key=lambda x: x[0])  # [(window, weight), ...]
    if not windows:
        windows = [(n_full, 1.0)]

    # 用最长窗口确定统一价格区间和分箱
    max_window = max(w for w, _ in windows)
    full_recent = df_full.tail(max_window)
    price_min = float(full_recent["low"].min())
    price_max = float(full_recent["high"].max())
    if price_max <= price_min:
        price_max = price_min * 1.01 + 1e-6
    edges = np.linspace(price_min, price_max, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2

    combined_sup = np.zeros(bins)
    combined_res = np.zeros(bins)
    combined_vol = np.zeros(bins)

    weight_sum = sum(wt for _, wt in windows)
    for window, wt in windows:
        norm_wt = wt / weight_sum
        c, tv, uv, dv, _ = build_volume_profile(
            df_full, lookback=window, bins=bins, edges=edges)
        sup_s, res_s = score_price_levels(
            df_full, c, tv, uv, dv, lookback=window)
        combined_sup += sup_s * norm_wt
        combined_res += res_s * norm_wt
        # 同时累计加权后的成交量分布（用于"是否有成交"过滤）
        if tv.max() > 0:
            combined_vol += (tv / tv.max()) * norm_wt

    # 距离惩罚：太远的价位优先级降低
    distance = np.abs(centers - close) / max(close, 1e-9)
    distance_penalty = np.exp(-distance * 8)
    final_sup_score = combined_sup * distance_penalty
    final_res_score = combined_res * distance_penalty

    below_mask = centers < close
    above_mask = centers > close

    def pick_levels(mask, score_arr, direction="support", k=2):
        candidates = []
        for i, price in enumerate(centers):
            if not mask[i] or combined_vol[i] <= 1e-9:
                continue
            candidates.append({"price": float(price),
                               "score": float(score_arr[i])})
        if not candidates:
            return []
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        picked = []
        min_gap = close * 0.015  # 同侧两条线最小间距 1.5%
        for item in candidates:
            p = item["price"]
            if all(abs(p - q) >= min_gap for q in picked):
                picked.append(p)
            if len(picked) >= k:
                break

        if direction == "support":
            picked.sort(reverse=True)   # 离现价近的在前
        else:
            picked.sort()
        return picked

    sup_prices = pick_levels(below_mask, final_sup_score, "support", 2)
    res_prices = pick_levels(above_mask, final_res_score, "resistance", 2)

    s1 = sup_prices[0] if len(sup_prices) >= 1 else close * 0.97
    s2 = sup_prices[1] if len(sup_prices) >= 2 else close * 0.93
    r1 = res_prices[0] if len(res_prices) >= 1 else close * 1.03
    r2 = res_prices[1] if len(res_prices) >= 2 else close * 1.07

    if s2 > s1: s1, s2 = s2, s1
    if r2 < r1: r1, r2 = r2, r1

    return {
        "支撑1": round(s1, 3),
        "支撑2": round(s2, 3),
        "压力1": round(r1, 3),
        "压力2": round(r2, 3),
    }, windows


def gen_tips(df, levels):
    last = df.iloc[-1]
    close, ma20, rsi = last["close"], last["MA20"], last["RSI"]
    ma10 = last["MA10"]
    chg = (close / df["close"].iloc[-2] - 1) * 100
    if close > ma10 > ma20: trend, cls = "🟢 多头趋势", "trend-bull"
    elif close < ma10 < ma20: trend, cls = "🔴 空头趋势", "trend-bear"
    else: trend, cls = "🟡 震荡整理", "trend-side"
    tips = []
    if close <= levels["支撑1"] * 1.02 and rsi < 40:
        tips.append(("success", "✅ 适合补仓", f"接近量价支撑 {levels['支撑1']:.2f}，RSI={rsi:.1f}"))
    elif close <= levels["支撑2"] * 1.02:
        tips.append(("success", "✅ 强支撑补仓", f"触及量价强支撑 {levels['支撑2']:.2f}"))
    if close >= levels["压力1"] * 0.98 and rsi > 65:
        tips.append(("warning", "⚠️ 适合减仓", f"接近量价压力 {levels['压力1']:.2f}，RSI={rsi:.1f}"))
    elif close >= levels["压力2"] * 0.98:
        tips.append(("warning", "⚠️ 强压力减仓", f"触及量价强压力 {levels['压力2']:.2f}"))
    stop = levels["支撑2"] * 0.97
    if close < stop:
        tips.append(("error", "🛑 触发止损", f"跌破量价强支撑下方3%（{stop:.2f}）"))
    if rsi > 75: tips.append(("warning", "⚠️ 超买预警", f"RSI={rsi:.1f}"))
    elif rsi < 25: tips.append(("success", "✅ 超卖机会", f"RSI={rsi:.1f}"))
    if not tips: tips.append(("info", "ℹ️ 观望", "未触及关键位"))
    return trend, cls, chg, tips

# ========== 图表（K线 + 成交量 + RSI） ==========
def plot_chart(df_full, df, name, levels, height=520):
    df = df.copy()
    df["x"] = df["date"].dt.strftime("%m-%d")
    vol_colors = np.where(df["close"] >= df["open"], "#e53935", "#43a047")
    
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.62, 0.20, 0.18],
        subplot_titles=("", "成交量", "RSI(14)"),
    )
    
    fig.add_trace(go.Candlestick(
        x=df["x"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="K线",
        increasing=dict(line=dict(color="#e53935", width=1.3), fillcolor="#e53935"),
        decreasing=dict(line=dict(color="#43a047", width=1.3), fillcolor="#43a047"),
        showlegend=False,
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df["x"], y=df["MA5"],  name="MA5",
                             line=dict(color="#ff9800", width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["x"], y=df["MA10"], name="MA10",
                             line=dict(color="#9c27b0", width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["x"], y=df["MA20"], name="MA20",
                             line=dict(color="#1976d2", width=1.8, dash="dash")), row=1, col=1)
    
    colors = {"支撑1": "#26a69a", "支撑2": "#1b5e20", "压力1": "#ef5350", "压力2": "#b71c1c"}
    for k, v in levels.items():
        fig.add_hline(y=v, line_dash="dot", line_color=colors[k], line_width=1.5,
                      annotation_text=f"{k} {v}", annotation_position="right",
                      annotation_font_size=10, annotation_font_color=colors[k], row=1, col=1)
    
    fig.add_trace(go.Bar(
        x=df["x"], y=df["volume"], name="成交量",
        marker=dict(color=vol_colors, line=dict(width=0)),
        showlegend=False, opacity=0.85,
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=df["x"], y=df["RSI"], name="RSI",
                             line=dict(color="#9c27b0", width=2),
                             fill="tozeroy", fillcolor="rgba(156,39,176,0.08)",
                             showlegend=False), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#e53935", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#43a047", line_width=1, row=3, col=1)
    
    fig.update_layout(
        height=height, hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0.5, xanchor="center",
                    font=dict(size=10), bgcolor="rgba(255,255,255,0.6)"),
        margin=dict(l=8, r=70, t=20, b=10),
        font=dict(size=11),
        plot_bgcolor="#fafafa",
        xaxis_rangeslider_visible=False,
        bargap=0.15,
    )
    fig.update_xaxes(type="category", showgrid=True, gridcolor="#eee",
                     tickfont=dict(size=10), nticks=8)
    fig.update_yaxes(showgrid=True, gridcolor="#eee", tickfont=dict(size=10))
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    return fig

# ========== 量价分布迷你图（多窗口综合） ==========
def plot_volume_profile(df_full, levels, windows, bins=30, height=260):
    """
    显示多时间框架加权融合后的量价分布。
    """
    n_full = len(df_full)
    max_window = max(w for w, _ in windows)
    full_recent = df_full.tail(max_window)
    price_min = float(full_recent["low"].min())
    price_max = float(full_recent["high"].max())
    if price_max <= price_min:
        price_max = price_min * 1.01 + 1e-6
    edges = np.linspace(price_min, price_max, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2

    up_total = np.zeros(bins)
    down_total = np.zeros(bins)
    weight_sum = sum(wt for _, wt in windows)
    for window, wt in windows:
        norm_wt = wt / weight_sum
        _, tv, uv, dv, _ = build_volume_profile(
            df_full, lookback=window, bins=bins, edges=edges)
        # 各窗口归一化后再加权，避免长窗口绝对量碾压短窗口
        max_tv = tv.max() if tv.max() > 0 else 1
        up_total += (uv / max_tv) * norm_wt
        down_total += (dv / max_tv) * norm_wt

    close = float(df_full["close"].iloc[-1])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=up_total, y=centers, orientation="h",
        marker=dict(color="#ef5350", line=dict(width=0)),
        name="上涨量", showlegend=False, opacity=0.85,
        hovertemplate="价位 %{y:.2f}<br>上涨量 %{x:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=down_total, y=centers, orientation="h",
        marker=dict(color="#43a047", line=dict(width=0)),
        name="下跌量", showlegend=False, opacity=0.85,
        hovertemplate="价位 %{y:.2f}<br>下跌量 %{x:.3f}<extra></extra>",
    ))
    
    fig.add_hline(y=close, line_dash="solid", line_color="#1976d2", line_width=1.5,
                  annotation_text=f"现价 {close:.2f}", annotation_position="right",
                  annotation_font_size=10, annotation_font_color="#1976d2")
    
    line_colors = {"支撑1": "#26a69a", "支撑2": "#1b5e20", "压力1": "#ef5350", "压力2": "#b71c1c"}
    for k, v in levels.items():
        fig.add_hline(y=v, line_dash="dot", line_color=line_colors[k], line_width=1.2,
                      annotation_text=k, annotation_position="left",
                      annotation_font_size=9, annotation_font_color=line_colors[k])
    
    win_str = " + ".join([f"{w}日×{int(wt*100)}%" for w, wt in windows])
    fig.update_layout(
        height=height, margin=dict(l=8, r=60, t=20, b=10),
        plot_bgcolor="#fafafa", font=dict(size=10),
        barmode="stack",
        title=dict(text=f"量价分布（综合：{win_str}）",
                   x=0.02, y=0.98, font=dict(size=10)),
    )
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eee", tickfont=dict(size=9))
    return fig

# ========== 主界面 ==========
with st.sidebar:
    st.markdown("## ⚙️ 设置")
    show_days = st.slider("显示天数", 5, 60, 10, 1)
    chart_h   = st.slider("图表高度", 380, 800, 540, 20)
    mid_lookback = st.slider("中期回溯（核心）", 30, 120, 60, 5,
                              help="支撑压力位会综合：短期20日 + 此中期 + 长期120日")
    bins      = st.slider("价格分箱数", 15, 60, 30, 5)
    if st.button("🔄 强制刷新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.caption("💡 显示窗口与支撑/压力计算窗口已解耦：")
    st.caption("• K线只画近 N 天")
    st.caption("• 关键位综合 短20+中可调+长120 三窗")
    st.caption(f"刷新：{datetime.now().strftime('%H:%M:%S')}")

st.markdown("# 📈 A股技术分析助手 · 多周期量价版")

tabs = st.tabs(list(TARGETS.keys()))

for tab, (name, info) in zip(tabs, TARGETS.items()):
    with tab:
        with st.spinner(f"加载 {name}..."):
            df_full, source, errors = fetch_data(info["code"], info["market"], 160)

        if df_full is None:
            st.error("❌ 所有数据源均失败")
            with st.expander("错误详情"):
                for e in errors: st.code(e)
            continue

        df_full = compute_indicators(df_full)
        df = df_full.tail(show_days).reset_index(drop=True)
        levels, windows = find_levels(df_full, df, mid_lookback=mid_lookback, bins=bins)
        trend, trend_cls, chg, tips = gen_tips(df_full, levels)
        last = df.iloc[-1]

        win_label = " + ".join([f"{w}日×{int(wt*100)}%" for w, wt in windows])
        st.markdown(
            f'<div class="info-bar">'
            f'<span>📡 <b>{source}</b> · 显示近 <b>{len(df)}</b> 日 · '
            f'最新 <b>{df["date"].iloc[-1].strftime("%Y-%m-%d")}</b> · '
            f'关键位综合 <b>{win_label}</b></span>'
            f'<span>趋势：<span class="trend-badge {trend_cls}">{trend}</span></span>'
            f'</div>',
            unsafe_allow_html=True)

        col_left, col_right = st.columns([2.2, 1], gap="small")
        
        with col_left:
            st.plotly_chart(plot_chart(df_full, df, name, levels, height=chart_h),
                            use_container_width=True,
                            config={"displayModeBar": False})
        
        with col_right:
            r1c1, r1c2 = st.columns(2)
            r1c1.metric("最新价", f"{last['close']:.2f}", f"{chg:+.2f}%")
            r1c2.metric("RSI(14)", f"{last['RSI']:.1f}")
            r2c1, r2c2 = st.columns(2)
            r2c1.metric(f"{show_days}日高", f"{df['high'].max():.2f}")
            r2c2.metric(f"{show_days}日低", f"{df['low'].min():.2f}")
            
            st.plotly_chart(
                plot_volume_profile(df_full, levels, windows, bins=bins, height=240),
                use_container_width=True, config={"displayModeBar": False})
            
            st.markdown("#### 🎯 综合关键位")
            rows_html = ""
            for k, v in levels.items():
                pct = (v / last['close'] - 1) * 100
                cls = "level-sup" if "支撑" in k else "level-res"
                rows_html += f'<tr><td class="{cls}">{k}</td><td>{v:.2f}</td><td>{pct:+.2f}%</td></tr>'
            st.markdown(
                f'<table class="level-table">'
                f'<thead><tr><th>类型</th><th>价位</th><th>距现价</th></tr></thead>'
                f'<tbody>{rows_html}</tbody></table>',
                unsafe_allow_html=True)
            
            st.markdown("#### 💡 操作建议")
            for level, title, content in tips:
                st.markdown(
                    f'<div class="signal-card signal-{level}">'
                    f'<b>{title}</b><br>{content}</div>',
                    unsafe_allow_html=True)

st.caption("⚠️ 支撑/压力位由短期(20日)+中期(可调)+长期(120日)三窗加权融合，结合成交量密集度、触达次数、反弹/回落、涨跌量占比综合评分，仅供参考，不构成投资建议。")