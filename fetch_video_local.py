import json
import os
import time
import requests
import urllib.request
import urllib.error
import re
import html
import http.cookiejar
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
APIYI_TOKEN = os.environ.get("OPENAI_API_KEY")

CHANNELS = [
    {"name": "Andrej Karpathy", "id": "UCXUPKJO5MZQN11PqgIvyuvQ"},
    {"name": "Stanford CS224U", "id": "UCBa5G_ESCn8Yd4vw5U-gIcg"},
    {"name": "Lex Fridman", "id": "UCSHZKyawb77ixDdsGog4iWA"},
    {"name": "Stanford HAI", "id": "UChugFTK0KyrES9terTid8vA"},
]

openai_client = OpenAI(
    api_key=APIYI_TOKEN,
    base_url="https://api.apiyi.com/v1"
)

def get_videos_from_channel(channel_id, max_results=3):
    """获取频道最新视频"""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'channelId': channel_id,
        'maxResults': max_results,
        'order': 'date',
        'type': 'video',
        'key': YOUTUBE_API_KEY
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    videos = []
    for item in data.get('items', []):
        videos.append({
            'video_id': item['id']['videoId'],
            'title': item['snippet']['title'],
            'published_at': item['snippet']['publishedAt'],
            'channel': item['snippet']['channelTitle'],
            'description': item['snippet']['description']
        })
    return videos



import yt_dlp

def get_transcript(video_id):
    """使用 yt-dlp 获取字幕"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'vtt',
        'cookiefile': 'cookies.txt',  # 使用 cookies 绕过限流
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # 获取字幕
            subtitles = info.get('automatic_captions', {}) or info.get('subtitles', {})
            
            if 'en' not in subtitles:
                print(f"  没有英文字幕")
                return None
            
            # 获取字幕 URL
            caption_url = subtitles['en'][0]['url']
            
            # 下载字幕内容
            import requests
            response = requests.get(caption_url, cookies=requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(ydl.cookiejar)))
            response.raise_for_status()
            
            # 解析 VTT 格式
            lines = response.text.split('\n')
            text_parts = []
            for line in lines:
                line = line.strip()
                if not line or '-->' in line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                    continue
                line = re.sub(r'<[^>]+>', '', line)
                if line:
                    text_parts.append(line)
            
            full_text = ' '.join(text_parts)
            if full_text:
                print(f"  获取字幕成功，长度: {len(full_text)}")
                return full_text
            else:
                print(f"  字幕为空")
                return None
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
        videos = get_videos_from_channel(channel['id'], max_results=3)
        
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