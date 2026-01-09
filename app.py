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
# --- 📸 上傳照片 API (扁平化改良版) ---
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # 1. 接收資料
        file = request.files.get('photo')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        note = request.form.get('note')
        nickname = request.form.get('nickname')
        area = request.form.get('area')

        # 2. 門神檢查：如果有缺資料，直接報錯踢出去
        if not file or not lat or not lng:
            return jsonify({
                'status': 'error', 
                'message': f'資料缺漏 Debug: lat={lat}, lng={lng}, file={file}'
            })

        # 3. 範圍檢查 (簡單版)
        try:
            if not (24.30 <= float(lat) <= 24.48 and 120.58 <= float(lng) <= 120.75):
                return jsonify({'status': 'error', 'message': '抱歉！這裡不是苑裡鎮喔 (座標不在範圍內) 📍'})
        except:
            pass # 如果座標轉不過來，就放過它，讓後面上傳

        # 4. 上傳照片
        if IS_PRODUCTION:
            upload_result = cloudinary.uploader.upload(file)
            image_url = upload_result['secure_url']
        else:
            image_url = "local_test.jpg"

        # 5. 寫入資料庫
        conn = get_db_connection()
        c = conn.cursor()
        
        # 根據環境選擇 SQL 指令
        sql = """
            INSERT INTO temples (lat, lng, image_url, note, nickname, area, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (lat, lng, image_url, note, nickname, area, datetime.now())
        
        if not IS_PRODUCTION:
             # 本機測試用 ? 當佔位符
            sql = sql.replace('%s', '?')

        c.execute(sql, params)
        conn.commit()
        conn.close()
        return jsonify({'message': 'Bingo! 抓到一隻土地公了！📸 成功插旗！🚩'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'系統錯誤: {str(e)}'})

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
                'id': row['id'],
                'lat': row['lat'],
                'lng': row['lng'],
                'image': row['image_url'],
                'note': row['note']
            })

        return jsonify(results)
    except:
        return jsonify([])

# --- 🔴 新增：刪除功能 ---
# --- 🔴 新增：刪除功能 ---
@app.route('/delete/<int:id>', methods=['POST'])
def delete_temple(id):
    try:
        # 檢查密碼 (預設 8888)
        password = request.form.get('password')
        if password != '8888':
            return jsonify({'status': 'error', 'message': '密碼錯誤！禁止刪除 🛡️'})

        # 連線資料庫並刪除
        conn = get_db_connection()
        c = conn.cursor()
        if IS_PRODUCTION:
             c.execute("DELETE FROM temples WHERE id = %s", (id,))
        else:
             c.execute("DELETE FROM temples WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '刪除成功！再見了 👋'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
# --- 🔴 刪除功能結束 ---

# --- 🛠️ 資料庫維修工具 (第二階段：擴充欄位) ---
@app.route('/fix_db_v2')
def fix_data_v2():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # 1. 新增 nickname (暱稱) 欄位
        c.execute("ALTER TABLE temples ADD COLUMN IF NOT EXISTS nickname TEXT;")
        # 2. 新增 area (地區) 欄位
        c.execute("ALTER TABLE temples ADD COLUMN IF NOT EXISTS area TEXT;")
        
        conn.commit()
        return "✅ 擴充成功！現在資料庫可以存「暱稱」和「地區」了！"
    except Exception as e:
        return f"維修報告: {e}"
    finally:
        conn.close()



if __name__ == '__main__':
    app.run(debug=True)
