# 使用官方 Python 基礎映像檔
FROM python:3.9-slim

# 安裝 FFmpeg (這是關鍵！)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# 建立暫存資料夾 (確保權限正確)
RUN mkdir -p temp_downloads

# 設定啟動指令
# 使用 gunicorn 啟動 app:app (檔名:變數名)
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:10000", "app:app", "--timeout", "300"]