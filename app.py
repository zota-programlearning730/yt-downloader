from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp
import os
import shutil
import zipfile
import time
import uuid # 用來產生唯一的暫存資料夾名稱

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

    # 1. 為這次下載建立一個唯一的暫存資料夾 (避免多人使用時檔案混在一起)
    task_id = str(uuid.uuid4())
    task_folder = os.path.join(BASE_TEMP_FOLDER, task_id)
    os.makedirs(task_folder)

    print(f"開始任務: {task_id}, URL: {url}")

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
    }

    if get_lyrics:
        ydl_options.update({
            'writesubtitles': True,
            'subtitleslangs': ['en', 'zh-Hant'],
        })

    try:
        # 2. 執行下載
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            ydl.download([url])

        # 3. 檢查下載了幾個檔案
        downloaded_files = os.listdir(task_folder)
        if not downloaded_files:
            return jsonify({'status': 'error', 'message': '找不到影片或下載失敗'}), 500

        # 4. 準備回傳的檔案路徑
        final_file_path = ""
        download_name = ""

        # 如果只有一個檔案 (且不是字幕檔)，直接回傳該檔案；否則全部壓縮
        mp3_files = [f for f in downloaded_files if f.endswith('.mp3')]
        
        if len(downloaded_files) == 1 and downloaded_files[0].endswith('.mp3'):
            # 單一 MP3
            final_file_path = os.path.join(task_folder, downloaded_files[0])
            download_name = downloaded_files[0]
        else:
            # 多個檔案或包含歌詞 -> 壓成 ZIP
            zip_filename = f"music_download_{task_id[:8]}.zip"
            zip_path = os.path.join(BASE_TEMP_FOLDER, zip_filename)
            zip_files(task_folder, zip_path)
            final_file_path = zip_path
            download_name = zip_filename

        # 5. 回傳檔案網址給前端 (前端會再發起一次 GET 請求來下載)
        # 為什麼不直接 send_file? 因為這裡是 AJAX POST，直接傳二進位流前端處理較複雜
        # 我們回傳一個下載連結，讓前端用 window.location.href 跳轉下載
        return jsonify({
            'status': 'success', 
            'download_url': f'/get-file/{task_id}/{download_name}'
        })

    except Exception as e:
        # 發生錯誤時清理暫存
        shutil.rmtree(task_folder, ignore_errors=True)
        return jsonify({'status': 'error', 'message': f'發生錯誤: {str(e)}'}), 500

@app.route('/get-file/<task_id>/<filename>')
def get_file(task_id, filename):
    """實際傳送檔案的路由"""
    # 這裡有點技巧：我們需要傳送檔案後刪除它
    
    task_folder = os.path.join(BASE_TEMP_FOLDER, task_id)
    # 如果是 zip，它在 BASE_TEMP_FOLDER 下；如果是 mp3，它在 task_folder 下
    
    file_path = ""
    if filename.endswith('.zip'):
        file_path = os.path.join(BASE_TEMP_FOLDER, filename)
    else:
        file_path = os.path.join(task_folder, filename)

    if not os.path.exists(file_path):
        return "File not found or expired", 404

    # 設定一個 callback，在請求結束後刪除檔案和資料夾
    @after_this_request
    def cleanup(response):
        try:
            if os.path.exists(file_path):
                os.remove(file_path) # 刪除檔案
            if os.path.exists(task_folder):
                shutil.rmtree(task_folder, ignore_errors=True) # 刪除暫存資料夾
            print(f"清理完成: {task_id}")
        except Exception as e:
            print(f"清理錯誤: {e}")
        return response

    return send_file(file_path, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)