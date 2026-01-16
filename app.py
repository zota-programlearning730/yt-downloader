from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp
import os
import shutil
import zipfile
import uuid
import syncedlyrics  # 新增：外部歌詞套件

app = Flask(__name__)

# 設定暫存根目錄
BASE_TEMP_FOLDER = 'temp_downloads'
if not os.path.exists(BASE_TEMP_FOLDER):
    os.makedirs(BASE_TEMP_FOLDER)

def zip_files(folder_path, output_path):
    """將資料夾內的檔案壓縮成 zip"""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), file)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    raw_urls = data.get('urls', '')  # 接收多行字串
    format_type = data.get('format', 'mp3') # 'mp3' or 'mp4'
    get_lyrics = data.get('lyrics', False)

    # 處理多網址：依換行符號切割，並去除空白
    url_list = [u.strip() for u in raw_urls.split('\n') if u.strip()]

    if not url_list:
        return jsonify({'status': 'error', 'message': '請至少輸入一個網址'}), 400

    task_id = str(uuid.uuid4())
    task_folder = os.path.join(BASE_TEMP_FOLDER, task_id)
    os.makedirs(task_folder)

    print(f"開始任務: {task_id}, 網址數量: {len(url_list)}")

    # === 設定 yt-dlp 參數 ===
# ... (前面的程式碼) ...

    # === 設定 yt-dlp 參數 ===
    ydl_options = {
        'outtmpl': f'{task_folder}/%(title)s.%(ext)s',
        'ignoreerrors': True,
        'noplaylist': False,
        
        # 1. 嘗試移除 cookies.txt 看看 (如果 cookies 失效會導致下載失敗)
        # 如果你確定 cookies 是新鮮且有效的，可以留著，不然建議先註解掉測試
        # 'cookiefile': 'cookies.txt', 
        
        # 2. 關鍵：模擬真實瀏覽器 User-Agent
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        
        # 3. 避免下載容易失敗的 HLS 分段串流 (你的 log 裡失敗的就是這種)
        # 告訴它優先選 "非 dash" 且 "非 hls" 的格式，這通常會比較穩定
        # 但如果是 MP3 下載，通常 bestaudio 就夠了，這邊主要針對影片
    }

    if format_type == 'mp3':
        ydl_options.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else: # mp4
        ydl_options.update({
            # 嘗試修改格式選擇邏輯：優先選有影片+聲音的單檔，選不到才合併
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    # ... (後面的程式碼) ...

    try:
        downloaded_titles = []
        
        # 迴圈處理每個網址
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            for url in url_list:
                try:
                    # 1. 下載影片/音樂
                    info = ydl.extract_info(url, download=True)
                    
                    # 獲取影片標題供歌詞搜尋使用
                    # 如果是播放清單，info 會是 entries，這裡簡化處理，只針對單影片優化歌詞
                    if 'entries' not in info:
                        title = info.get('title', '')
                        downloaded_titles.append(title)
                        
                        # 2. 歌詞下載 (使用 syncedlyrics)
                        if get_lyrics and title:
                            print(f"正在搜尋歌詞: {title}")
                            try:
                                # 搜尋並儲存 .lrc 檔案
                                lrc_content = syncedlyrics.search(title)
                                if lrc_content:
                                    lrc_filename = os.path.join(task_folder, f"{title}.lrc")
                                    with open(lrc_filename, "w", encoding="utf-8") as f:
                                        f.write(lrc_content)
                            except Exception as e:
                                print(f"歌詞下載失敗 ({title}): {e}")

                except Exception as e:
                    print(f"單一網址下載錯誤: {e}")
                    continue

        # 檢查資料夾內是否有檔案
        files = os.listdir(task_folder)
        if not files:
            return jsonify({'status': 'error', 'message': '下載失敗，可能是 YouTube 封鎖了伺服器 IP，或 Cookies 失效。'}), 500

        # 打包邏輯：如果只有一個檔案且不是 zip，直接回傳；否則打包
        # 注意：如果有歌詞檔(.lrc) + 音樂檔(.mp3)，也應該打包，方便使用者一次下載
        media_files = [f for f in files if f.endswith('.mp3') or f.endswith('.mp4')]
        
        # 如果只有一個媒體檔案，且沒有歌詞檔案，才直接傳檔案
        if len(files) == 1 and (files[0].endswith('.mp3') or files[0].endswith('.mp4')):
            final_file_path = os.path.join(task_folder, files[0])
            download_name = files[0]
        else:
            # 多個檔案 (多首歌 或 一首歌+歌詞)，全部打包
            zip_filename = f"yt_downloads_{task_id[:8]}.zip"
            zip_path = os.path.join(BASE_TEMP_FOLDER, zip_filename)
            zip_files(task_folder, zip_path)
            final_file_path = zip_path
            download_name = zip_filename

        return jsonify({
            'status': 'success', 
            'download_url': f'/get-file/{task_id}/{download_name}'
        })

    except Exception as e:
        shutil.rmtree(task_folder, ignore_errors=True)
        return jsonify({'status': 'error', 'message': f'系統錯誤: {str(e)}'}), 500

@app.route('/get-file/<task_id>/<filename>')
def get_file(task_id, filename):
    task_folder = os.path.join(BASE_TEMP_FOLDER, task_id)
    if filename.endswith('.zip'):
        file_path = os.path.join(BASE_TEMP_FOLDER, filename)
    else:
        file_path = os.path.join(task_folder, filename)

    if not os.path.exists(file_path):
        return "File not found or expired", 404

    @after_this_request
    def cleanup(response):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(task_folder):
                shutil.rmtree(task_folder, ignore_errors=True)
        except Exception as e:
            print(f"清理錯誤: {e}")
        return response

    return send_file(file_path, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True, host='0.0.0.0', port=port)