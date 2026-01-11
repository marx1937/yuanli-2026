from flask import Flask, render_template, request, jsonify, send_from_directory
import cloudinary
import cloudinary.uploader
import os
import psycopg2

app = Flask(__name__)

# --- 設定區 ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS land_gods (
                id SERIAL PRIMARY KEY,
                image_url TEXT NOT NULL,
                lat DOUBLE PRECISION,
                lng DOUBLE PRECISION,
                note TEXT,
                nickname TEXT,
                area TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("資料庫連線成功")
    except Exception as e:
        print("資料庫錯誤:", e)

init_db()

# ================= 路由區 (導航核心) =================

# 1. 首頁 (這就是你現在 404 缺少的東西！)
@app.route('/')
def home():
    return render_template('index.html')

# 2. 查報頁
@app.route('/report')
def report_page():
    return render_template('upload.html')

# 3. 地圖頁
@app.route('/map')
def map_page():
    return render_template('map.html')

# 4. 顯示歡迎圖片 (讀取根目錄照片)
@app.route('/welcome.jpg')
def welcome_image():
    try:
        return send_from_directory('.', 'welcome.jpg')
    except:
        return "圖片讀取錯誤", 404

# 5. 排行榜 API (給首頁用的)
@app.route('/api/rank')
def get_rank():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT nickname, COUNT(*) as count 
            FROM land_gods 
            GROUP BY nickname 
            ORDER BY count DESC 
            LIMIT 5;
        ''')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        rank_data = []
        for row in rows:
            rank_data.append({
                'name': row[0] if row[0] else "熱心串友",
                'count': row[1]
            })
        return jsonify(rank_data)
    except Exception as e:
        print(e)
        return jsonify([])

# 6. 地圖資料 API
@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT image_url, lat, lng, note, nickname, area, created_at FROM land_gods;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    data = []
    for row in rows:
        data.append({
            'image_url': row[0],
            'lat': row[1],
            'lng': row[2],
            'note': row[3],
            'nickname': row[4],
            'area': row[5],
            'created_at': str(row[6])
        })
    return jsonify(data)

# 7. 上傳功能
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['photo']
    lat = request.form['lat']
    lng = request.form['lng']
    note = request.form['note']
    nickname = request.form['nickname']
    area = request.form['area']

    if file:
        upload_result = cloudinary.uploader.upload(file)
        image_url = upload_result['secure_url']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO land_gods (image_url, lat, lng, note, nickname, area) VALUES (%s, %s, %s, %s, %s, %s)',
            (image_url, lat, lng, note, nickname, area)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success', 'url': image_url})
    
    return jsonify({'status': 'error'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
