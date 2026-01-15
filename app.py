import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
import cloudinary
import cloudinary.uploader
from math import radians, cos, sin, asin, sqrt
# 👇 新增這個：地名翻譯官
from geopy.geocoders import Nominatim 

app = Flask(__name__)

# --- 設定密鑰 (Session 用) ---
app.secret_key = os.environ.get('SECRET_KEY', 'yuanli_secret_key')
ADMIN_PASSWORD = 'ytc@358'

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

# --- 🔥 新增功能：座標轉地名 (反向地理編碼) ---
def get_location_name(lat, lng):
    try:
        # user_agent 必須是唯一的，隨便取個名字
        geolocator = Nominatim(user_agent="yuanli_god_hunter_2026_render")
        location = geolocator.reverse(f"{lat}, {lng}", language='zh-tw')
        
        address = location.raw.get('address', {})
        # 抓取順序：村里 > 鄰居 > 鄉鎮
        area = address.get('village') or address.get('neighbourhood') or address.get('town')
        
        if area:
            # 確保前面有掛上 "苑裡" 兩個字，看起來比較整齊
            if "苑裡" not in area:
                return f"苑裡 {area}"
            return area
        else:
            return "苑裡某處"
    except Exception as e:
        print(f"翻譯失敗: {e}")
        return "苑裡某處"

# ================= 頁面路由 (Routes) =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map')
def map_page():
    return render_template('map.html')

@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

@app.route('/gallery')
def gallery_page():
    return render_template('gallery.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/admin')
def admin_page():
    if not session.get('is_admin'):
        return redirect(url_for('login_page'))
    return render_template('admin.html')

@app.route('/report')
@app.route('/upload_page')
def show_upload_page():
    return render_template('upload.html')

# ================= 功能邏輯 (API) =================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': '密碼錯誤'})

# 2. 核心：上傳功能 (包含重複檢查 + 🔥 自動翻譯地名)
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template('upload.html')

    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': '沒有檔案'})
    
    file = request.files['photo']
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    note = request.form.get('note')
    nickname = request.form.get('nickname')
    
    # 這裡原本是 request.form.get('area')，我們現在要用後端算出來的
    
    if file and lat and lng:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # --- 🛑 重複地點檢查 ---
            cur.execute("SELECT lat, lng FROM land_gods")
            rows = cur.fetchall()
            
            for row in rows:
                db_lat = row[0]
                db_lng = row[1]
                dist = haversine(float(lng), float(lat), db_lng, db_lat)
                
                if dist < -1: # 注意：你原本設 -1 是關閉檢查，如果開啟要改成 < 0.05
                    conn.close()
                    return jsonify({'status': 'pending', 'message': '地點重複，已送審'})
            
            # --- 🔥 關鍵：計算地名 ---
            # 這裡呼叫我們的翻譯機
            detected_area = get_location_name(lat, lng)
            print(f"新座標: {lat}, {lng} -> 翻譯結果: {detected_area}")

            # --- ✅ 上傳 Cloudinary ---
            upload_result = cloudinary.uploader.upload(file)
            image_url = upload_result['secure_url']

            # --- 💾 寫入資料庫 ---
            # 注意：最後一個欄位 area 改用 detected_area
            cur.execute("INSERT INTO land_gods (image_url, lat, lng, note, nickname, area) VALUES (%s, %s, %s, %s, %s, %s)",
                        (image_url, float(lat), float(lng), note, nickname, detected_area))
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({'status': 'success', 'url': image_url, 'area': detected_area})

        except Exception as e:
            print("Error:", e)
            return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({'status': 'error', 'message': '資料不完整'})

# 3. 提供地圖資料 API
@app.route('/api/locations')
def get_locations():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, lat, lng, area, note, image_url, nickname, created_at FROM land_gods')
    rows = cur.fetchall()
    conn.close()
    
    locations = []
    for row in rows:
        locations.append({
            'id': row[0],
            'lat': row[1],
            'lng': row[2],
            'area': row[3], # 這裡就會讀到 "苑裡 客庄里" 了
            'note': row[4],
            'image_url': row[5],
            'nickname': row[6],
            'timestamp': str(row[7])
        })
    return jsonify(locations)

# ================= 管理員專用 API =================

@app.route('/api/admin/all_data')
def get_all_data():
    if not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': '權限不足'})

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, area, nickname, note, image_url, created_at, lat, lng 
        FROM land_gods 
        ORDER BY id DESC
    ''')
    rows = cur.fetchall()
    conn.close()

    data = []
    for row in rows:
        data.append({
            'id': row[0],
            'area': row[1],
            'nickname': row[2],
            'note': row[3],
            'image_url': row[4],
            'created_at': str(row[5]),
            'lat': row[6],
            'lng': row[7]
        })

    return jsonify(data)

# ================= 排行榜專用 API =================
@app.route('/api/leaderboard_data')
def leaderboard_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT nickname, COUNT(*) as count 
            FROM land_gods 
            GROUP BY nickname 
            ORDER BY count DESC 
            LIMIT 10
        """)
        user_rows = cur.fetchall()

        cur.execute("""
            SELECT area, COUNT(*) as count 
            FROM land_gods 
            GROUP BY area 
            ORDER BY count DESC 
            LIMIT 10
        """)
        area_rows = cur.fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'by_user': [{'name': r[0] or '熱心串友', 'count': r[1]} for r in user_rows],
            'by_area': [{'name': r[0] or '未知區域', 'count': r[1]} for r in area_rows]
        })

    except Exception as e:
        print("排行榜錯誤:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/delete', methods=['POST'])
def delete_location():
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': '權限不足，請先登入'})

    location_id = request.form.get('id')
    
    if not location_id:
        return jsonify({'success': False, 'message': '找不到 ID'})

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM land_gods WHERE id = %s', (location_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "已成功刪除"})
        
    except Exception as e:
        print("刪除失敗:", e)
        return jsonify({"success": False, "message": "資料庫錯誤"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
