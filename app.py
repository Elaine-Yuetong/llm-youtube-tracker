import streamlit as st
import json
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LLM YouTube Tracker", layout="wide")

st.title("🤖 LLM YouTube 内容追踪表")
st.caption(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 读取数据
try:
    with open("data/videos.json", "r", encoding="utf-8") as f:
        videos = json.load(f)
except FileNotFoundError:
    st.error("暂无数据，请先运行 fetch_videos.py")
    st.stop()

# 转成DataFrame
df = pd.DataFrame(videos)

# 显示表格
st.dataframe(
    df[["title", "channel", "topics", "key_point", "relation", "published_at"]],
    column_config={
        "title": "视频标题",
        "channel": "频道",
        "topics": "LLM主题",
        "key_point": "核心观点",
        "relation": "与其他频道关系",
        "published_at": "发布时间"
    },
    use_container_width=True,
    height=600
)

# 统计信息
st.sidebar.header("📊 统计")
st.sidebar.metric("总视频数", len(videos))
st.sidebar.metric("覆盖频道", len(df["channel"].unique()))

# 按频道分组展示
st.sidebar.header("📁 按频道查看")
selected_channel = st.sidebar.selectbox("选择频道", ["全部"] + list(df["channel"].unique()))
if selected_channel != "全部":
    filtered = df[df["channel"] == selected_channel]
    st.dataframe(filtered[["title", "topics", "key_point"]])