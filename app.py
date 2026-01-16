from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp
import os
import shutil
import zipfile
import uuid

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
    url = data.get('url')
    get_lyrics = data.get('lyrics')

    if not url:
        return jsonify({'status': 'error', 'message': '請輸入網址'}), 400

    task_id = str(uuid.uuid4())
    task_folder = os.path.join(BASE_TEMP_FOLDER, task_id)
    os.makedirs(task_folder)

    print(f"開始任務: {task_id}, URL: {url}")

    # === 關鍵修改：加入 User-Agent 偽裝，防止被擋 ===
    ydl_options = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'{task_folder}/%(title)s.%(ext)s',
        'ignoreerrors': True,
        'noplaylist': False,
        # 偽裝成 Windows 電腦上的 Chrome 瀏覽器
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        },
        'cookiefile': 'cookies.txt',  # 加入這行，讀取同一層目錄下的 cookies.txt
    }
    # ============================================

    # if get_lyrics:
    #     ydl_options.update({
    #         'writesubtitles': True,
    #         'subtitleslangs': ['en', 'zh-Hant'],
    #     })
    # ... (前面的 ydl_options 保持不變) ...

    # # === 修改這一段：增強歌詞下載邏輯 ===
    # if get_lyrics:
    #     ydl_options.update({
    #         # 1. 下載創作者手動上傳的字幕
    #         'writesubtitles': True,
            
    #         # 2. 關鍵！如果沒有手動字幕，就下載 YouTube 自動產生的字幕
    #         'writeautomaticsub': True,
            
    #         # 3. 抓取更多語言變體
    #         # 'en.*' 代表所有英文 (en-US, en-UK...)
    #         # 'zh.*' 代表所有中文 (zh-TW, zh-Hant, zh-CN...)
    #         # 'ja' 加入日文，因為很多動漫歌需要
    #         'subtitleslangs': ['en.*', 'zh.*', 'ja'],
            
    #         # 4. 將字幕轉檔為最通用的 .srt 格式 (原本可能是 vtt)
    #         'postprocessors': [{
    #             # 這是原本的音訊轉換
    #             'key': 'FFmpegExtractAudio',
    #             'preferredcodec': 'mp3',
    #             'preferredquality': '192',
    #         }, {
    #             # 這是新增的：字幕轉換
    #             'key': 'FFmpegSubtitlesConvertor',
    #             'format': 'srt',
    #         }],
    #     })
    # ==================================

    # === 修改這一段：增強歌詞下載邏輯 ===
    # 在 app.py 找到這一段並修改
    if get_lyrics:
        ydl_options.update({
            'writesubtitles': True,
            'writeautomaticsub': True,
            
            # === 修改這裡：移除 .*，精確指定語言 ===
            # 這樣只會下載這三種，不會重複抓一堆變體
            'subtitleslangs': ['en', 'zh-Hant', 'ja'], 
            # ====================================

            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }, {
                'key': 'FFmpegSubtitlesConvertor',
                'format': 'srt',
            }],
        })
    # ==================================

    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            ydl.download([url])

        downloaded_files = os.listdir(task_folder)
        if not downloaded_files:
            # 嘗試捕捉更詳細的錯誤
            return jsonify({'status': 'error', 'message': '下載失敗：可能是 YouTube 封鎖了伺服器 IP，或影片有版權限制。'}), 500

        # 處理檔案回傳邏輯
        mp3_files = [f for f in downloaded_files if f.endswith('.mp3')]
        if len(downloaded_files) == 1 and downloaded_files[0].endswith('.mp3'):
            final_file_path = os.path.join(task_folder, downloaded_files[0])
            download_name = downloaded_files[0]
        else:
            zip_filename = f"music_download_{task_id[:8]}.zip"
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
    # === 關鍵修改：解決 Render Port 錯誤 ===
    # 自動抓取環境變數 PORT，如果沒有就用 10000 (Render 預設)
    port = int(os.environ.get("PORT", 10000))
    # 綁定 0.0.0.0 讓外部可以連線
    app.run(debug=True, host='0.0.0.0', port=port)