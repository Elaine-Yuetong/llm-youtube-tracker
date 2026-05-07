import json
import os
import time
from datetime import datetime
from googleapiclient.discovery import build
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi



YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
APIYI_TOKEN = os.environ.get("OPENAI_API_KEY")  # 注意：GitHub Secrets 里我们用 OPENAI_API_KEY 这个名字
# 选3个LLM博主
CHANNELS = [
    {"name": "Andrej Karpathy", "id": "UCgM3vYNYOgB6Ux3Sq1nf8rA"},
    {"name": "Yannic Kilcher", "id": "UCZHmQk67mSJgfCCTn7xBfew"},
    {"name": "Two Minute Papers", "id": "UCbfYPyITQ-7l4upoX8nvctg"},
]
# ==============================

# 初始化客户端
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
openai_client = OpenAI(
    api_key=APIYI_TOKEN,
    base_url="https://api.apiyi.com/v1"
)

def get_videos_from_channel(channel_id, max_results=5):
    """获取频道最新视频"""
    request = youtube.search().list(
        part='snippet',
        channelId=channel_id,
        order='date',
        type='video',
        maxResults=max_results
    )
    response = request.execute()
    
    videos = []
    for item in response['items']:
        videos.append({
            'video_id': item['id']['videoId'],
            'title': item['snippet']['title'],
            'published_at': item['snippet']['publishedAt'],
            'channel': item['snippet']['channelTitle'],
            'description': item['snippet']['description']
        })
    return videos

import yt_dlp
import requests
import re

def get_transcript(video_id):
    """用 yt-dlp + cookies 获取字幕"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'vtt',
        'cookiefile': 'cookies.txt',  # 使用 cookies 绕过限速
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # 获取自动生成的字幕
            subtitles = info.get('automatic_captions', {})
            if not subtitles:
                subtitles = info.get('subtitles', {})
            
            if 'en' not in subtitles:
                print(f"  没有英文字幕")
                return None
            
            # 获取字幕 URL
            caption_url = subtitles['en'][0]['url']
            
            # 下载字幕内容
            response = requests.get(caption_url)
            response.raise_for_status()
            
            # 解析 VTT 格式
            lines = response.text.split('\n')
            text_parts = []
            for line in lines:
                line = line.strip()
                if not line or '-->' in line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                    continue
                # 去掉 HTML 标签
                line = re.sub(r'<[^>]+>', '', line)
                if line:
                    text_parts.append(line)
            
            full_text = ' '.join(text_parts)
            print(f"  获取字幕成功，长度: {len(full_text)}")
            return full_text
    except Exception as e:
        print(f"  获取字幕失败: {e}")
        return None

def summarize_with_gpt(transcript, title):
    """用GPT总结视频内容"""
    prompt = f"""
你正在分析一个关于LLM（大语言模型）的YouTube视频。

视频标题：{title}

内容（前3000字符）：
{transcript[:3000]}

请用中文回答以下问题，输出格式为JSON：
1. topics: 这个视频讲了哪些LLM相关主题？（用列表形式，如["Transformer架构", "RLHF", "MoE"]）
2. key_point: 这个视频的核心观点是什么？（1-2句话）
3. relation: 这个视频可能和其他LLM博主的内容有什么关系？（如果没有明显关系，写"独立内容"）

只输出JSON，不要有其他文字。
"""
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    content = response.choices[0].message.content
    content = content.strip()
    
    # 清理 markdown 代码块
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    try:
        result = json.loads(content)
        return result
    except json.JSONDecodeError as e:
        print(f"  JSON解析失败: {e}")
        return {
            "topics": ["解析失败"],
            "key_point": content[:200] if content else "无法获取总结",
            "relation": "未知"
        }

def main():
    all_videos = []
    
    for channel in CHANNELS:
        print(f"正在处理频道: {channel['name']}")
        videos = get_videos_from_channel(channel['id'], max_results=5)
        
        for video in videos:
            print(f"  处理视频: {video['title'][:50]}...")
            
            transcript = get_transcript(video['video_id'])
            
            if transcript:
                summary = summarize_with_gpt(transcript, video['title'])
            else:
                summary = {
                    "topics": ["无法获取字幕"],
                    "key_point": video['description'][:200] if video['description'] else "无字幕，无法分析",
                    "relation": "无法判断"
                }
            
            all_videos.append({
                "video_id": video['video_id'],
                "title": video['title'],
                "channel": video['channel'],
                "published_at": video['published_at'],
                "topics": summary.get("topics", []),
                "key_point": summary.get("key_point", ""),
                "relation": summary.get("relation", ""),
                "last_updated": datetime.now().isoformat()
            })
            
            print(f"    等待5秒...")
            time.sleep(5)
        
        print(f"  频道处理完成，等待10秒...")
        time.sleep(10)
    
    os.makedirs("data", exist_ok=True)
    with open("data/videos.json", "w", encoding="utf-8") as f:
        json.dump(all_videos, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成！共处理 {len(all_videos)} 个视频")
    print(f"数据已保存到 data/videos.json")

if __name__ == "__main__":
    main()