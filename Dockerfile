FROM python:3.9-slim

# 安裝 FFmpeg (下載轉 MP3 必須)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p temp_downloads

# 設定環境變數 PORT，預設 10000
ENV PORT=10000

# 這裡使用 gunicorn 啟動，比 python app.py 更穩定
# 注意：它會自動讀取上面的 PORT 變數
CMD gunicorn -w 2 -b 0.0.0.0:$PORT app:app --timeout 300