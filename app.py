import os
from flask import Flask, render_template, request, jsonify
import psycopg2
import cloudinary
import cloudinary.uploader
# 👇 這裡就是你原本缺少的數學工具包
from math import radians, cos, sin, asin, sqrt

app = Flask(__name__)

# --- 設定 Cloudinary (圖片雲端) ---
# ⚠️ 請確保你的環境變數裡有設定 CLOUDINARY_URL，或是直接填入你的 Key
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# --- 數學公式：計算地球兩點距離 (Haversine) ---
def haversine(lon1, lat1, lon2, lat2):
    # 將十進制度數轉化為弧度
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine公式
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # 地球平均半徑，單位為公里
    return c * r

# --- 資料庫連線 ---
def get_db_connection():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn

# ================= 路由區 (Routes) =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_page')
def upload_page():
    return render_template('upload.html')

@app.route('/map')
def map_page():
    return render_template('map.html')

# --- 接收上傳資料 (核心功能) ---
@app.route('/upload', methods=['POST'])
def upload_file():
    # 1. 檢查有沒有檔案
    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': '沒有檔案'})
    
    file = request.files['photo']
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    note = request.form.get('note')
    nickname = request.form.get('nickname')
    area = request.form.get('area')

    # 確保資料完整
    if file and lat and lng:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # --- 🛑 重複地點檢查 (守門員) ---
            # 2. 先把所有土地公的位置抓出來
            cur.execute("SELECT lat, lng FROM land_gods")
            rows = cur.fetchall()
            
            for row in rows:
                db_lat = row[0]
                db_lng = row[1]
                
                # 計算距離 (單位：公里)
                # ⚠️ 測試模式：設定 0.5 (500公尺)，方便你在家測試
                # 測試成功後，記得改回 0.05 (50公尺)
                dist = haversine(float(lng), float(lat), db_lng, db_lat)
                
                # 如果距離太近，就擋下來
                if dist < 0.5: 
                    conn.close()
                    print(f"擋下重複資料！距離僅 {dist:.3f} 公里")
                    # 回傳 pending 狀態，讓前端跳出黃色視窗
                    return jsonify({'status': 'pending', 'message': '地圖上已有此地點'})
            
            # --- ✅ 通過檢查，開始上傳 ---

            # 3. 上傳圖片到 Cloudinary
            upload_result = cloudinary.uploader.upload(file)
            image_url = upload_result['secure_url']

            # 4. 寫入資料庫
            cur.execute("INSERT INTO land_gods (image_url, lat, lng, note, nickname, area) VALUES (%s, %s, %s, %s, %s, %s)",
                        (image_url, float(lat), float(lng), note, nickname, area))
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({'status': 'success', 'url': image_url})

        except Exception as e:
            print("上傳錯誤:", e)
            return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({'status': 'error', 'message': '資料不完整'})

# --- 取得所有地點 (給地圖用) ---
@app.route('/api/locations')
def get_locations():
    conn = get_db_connection()
    cur = conn.cursor()
    # 抓取所有需要的欄位
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
