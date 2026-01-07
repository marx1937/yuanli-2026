import os
import sqlite3
import psycopg2
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import cloudinary
import cloudinary.uploader
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# --- 設定區 ---
# 判斷是否在 Render 環境
IS_PRODUCTION = os.environ.get('RENDER') is not None

# 設定 Cloudinary (照片雲端)
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# --- 資料庫連線 ---
def get_db_connection():
    if IS_PRODUCTION:
        # 雲端模式：連線 PostgreSQL
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    else:
        # 本機模式：連線 SQLite
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
    return conn

# --- 初始化資料庫 ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    if IS_PRODUCTION:
        # PostgreSQL 語法
        c.execute('''CREATE TABLE IF NOT EXISTS temples (
            id SERIAL PRIMARY KEY,
            lat REAL,
            lng REAL,
            image_url TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    else:
        # SQLite 語法
        c.execute('''CREATE TABLE IF NOT EXISTS temples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL,
            lng REAL,
            image_url TEXT,
            note TEXT,
            created_at TEXT
        )''')
        
    conn.commit()
    conn.close()

# 啟動時執行一次初始化
try:
    init_db()
except Exception as e:
    print(f"初始化訊息: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        file = request.files.get('photo')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        note = request.form.get('note')

        if file and lat and lng:
            # 1. 上傳照片
            if IS_PRODUCTION:
                upload_result = cloudinary.uploader.upload(file)
                image_url = upload_result['secure_url']
            else:
                image_url = "local_test.jpg"

            # 2. 寫入資料庫
            conn = get_db_connection()
            c = conn.cursor()
            
            if IS_PRODUCTION:
                c.execute("INSERT INTO temples (lat, lng, image_url, note, created_at) VALUES (%s, %s, %s, %s, NOW())",
                          (lat, lng, image_url, note))
            else:
                c.execute("INSERT INTO temples (lat, lng, image_url, note, created_at) VALUES (?, ?, ?, ?, ?)",
                          (lat, lng, image_url, note, datetime.now()))
            
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': '土地公登錄成功！'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({'status': 'error', 'message': '資料不完整'})

@app.route('/api/temples')
def get_temples():
    try:
        conn = get_db_connection()
        if IS_PRODUCTION:
            c = conn.cursor(cursor_factory=RealDictCursor)
        else:
            c = conn.cursor()
            
        c.execute("SELECT * FROM temples")
        rows = c.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'lat': row['lat'],
                'lng': row['lng'],
                'image': row['image_url'],
                'note': row['note']
            })
        return jsonify(results)
    except:
        return jsonify([])

if __name__ == '__main__':
    app.run(debug=True)
