import os
from flask import Flask, render_template, request, jsonify
import psycopg2
import cloudinary
import cloudinary.uploader
# 數學公式包
from math import radians, cos, sin, asin, sqrt

app = Flask(__name__)

# --- Cloudinary 設定 ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# --- 數學公式：計算距離 ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 
    return c * r

# --- 資料庫連線 ---
def get_db_connection():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn

# ================= 路由設定 =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map')
def map_page():
    return render_template('map.html')

# ⚠️ 救命稻草：不管首頁連到哪，這些路徑通通導向「上傳頁」
@app.route('/report')
@app.route('/upload_page')
def show_upload_page():
    return render_template('upload.html')

# --- 核心：上傳功能 (GET=看頁面, POST=傳資料) ---
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    # 🟢 如果是 GET (瀏覽器要看頁面)
    if request.method == 'GET':
        return render_template('upload.html')

    # 🔴 如果是 POST (Ajax 要傳資料)
    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': '沒有檔案'})
    
    file = request.files['photo']
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    note = request.form.get('note')
    nickname = request.form.get('nickname')
    area = request.form.get('area')

    if file and lat and lng:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # --- 🛑 重複地點檢查 (0.5公里測試版) ---
            cur.execute("SELECT lat, lng FROM land_gods")
            rows = cur.fetchall()
            
            for row in rows:
                db_lat = row[0]
                db_lng = row[1]
                # 測試設定：0.5 (500公尺)，測試完記得改回 0.05
                dist = haversine(float(lng), float(lat), db_lng, db_lat)
                
                if dist < 0.5: 
                    conn.close()
                    print(f"重複擋下！距離: {dist:.3f} km")
                    return jsonify({'status': 'pending', 'message': '地點重複'})
            
            # --- ✅ 開始上傳 ---
            upload_result = cloudinary.uploader.upload(file)
            image_url = upload_result['secure_url']

            cur.execute("INSERT INTO land_gods (image_url, lat, lng, note, nickname, area) VALUES (%s, %s, %s, %s, %s, %s)",
                        (image_url, float(lat), float(lng), note, nickname, area))
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({'status': 'success', 'url': image_url})

        except Exception as e:
            print("Error:", e)
            return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({'status': 'error', 'message': '資料不完整'})

# --- API: 給地圖抓資料用的 ---
@app.route('/api/locations')
def get_locations():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, lat, lng, image_url, note, nickname, area, created_at FROM land_gods;')
    rows = cur.fetchall()
    conn.close()
    
    locations = []
    for row in rows:
        locations.append({
            'id': row[0],
            'lat': row[1],
            'lng': row[2],
            'image_url': row[3],
            'note': row[4],
            'nickname': row[5],
            'area': row[6],
            'created_at': row[7]
        })
    return jsonify(locations)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
