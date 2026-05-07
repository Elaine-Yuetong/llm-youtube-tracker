import yt_dlp

def get_transcript_test(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print("可用的字幕语言:", list(info.get('automatic_captions', {}).keys()))
            print("手动字幕:", list(info.get('subtitles', {}).keys()))
    except Exception as e:
        print(f"错误: {e}")

# 测试一个Yannic的视频
get_transcript_test("xHi8PUIVyoo")