FROM python:3.9-slim

# === 關鍵修改：加入 nodejs ===
# yt-dlp 需要 nodejs 來執行複雜的 YouTube 解密腳本 (n-token)
# 同時保留 ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg nodejs && \
    apt-get clean

WORKDIR /app

# 設定 Python 輸出不緩衝 (方便看 Log)
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
# 強制升級 yt-dlp 到最新版 (避免快取舊版本)
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

RUN mkdir -p temp_downloads

ENV PORT=10000

# 設定較長的 timeout，避免批次下載時被切斷
CMD gunicorn -w 2 -b 0.0.0.0:$PORT app:app --timeout 1000