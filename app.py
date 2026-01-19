import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
import cloudinary
import cloudinary.uploader
import cloudinary.api
from math import radians, cos, sin, asin, sqrt
from geopy.geocoders import Nominatim 

app = Flask(__name__)

# --- 設定密鑰 ---
app.secret_key = os.environ.get('SECRET_KEY', 'yuanli_secret_key_888')
ADMIN_PASSWORD = '8888'  # 🔥 設定為新密碼

# --- Cloudinary 設定 ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# --- 資料庫連線 ---
def get_db_connection():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn

# --- 自動建表 ---
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS land_gods (
                id SERIAL PRIMARY KEY,
                image_url TEXT NOT NULL,
                lat FLOAT,
                lng FLOAT,
                note TEXT,
                nickname TEXT,
                area TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ 建表失敗: {e}")

try:
    init_db()
except:
    pass

# --- 距離計算 (Haversine) ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 
    return c * r

# --- 座標轉地名 ---
def get_location_name(lat, lng):
    try:
        geolocator = Nominatim(user_agent="yuanli_god_hunter_2026_final_v2")
        location = geolocator.reverse(f"{lat}, {lng}", language='zh-tw')
        address = location.raw.get('address', {})
        area = address.get('village') or address.get('neighbourhood') or address.get('town')
        if area:
            if "苑裡" not in area:
                return f"苑裡 {area}"
            return area
        else:
            return "苑裡某處"
    except:
        return "苑裡某處"

# ================= 頁面路由 =================
@app.route('/')
def index(): return render_template('index.html')

@app.route('/map')
def map_page(): return render_template('map.html')

@app.route('/leaderboard')
def leaderboard_page(): return render_template('leaderboard.html')

@app.route('/gallery')
def gallery_page(): return render_template('gallery.html')

@app.route('/report')
@app.route('/upload_page')
def show_upload_page(): return render_template('upload.html')

# ================= 🔐 查報系統管理後台 (Admin System) =================

# 1. 登入頁面 (紅色大門)
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin/dashboard')
        else:
            # 這裡為了簡單，直接重新導向並在此處不使用 flash 避免 secret_key 問題，
            # 實際上 template 還是可以接收參數，或直接 reload
            return render_template('admin_login.html', error="密碼錯誤")
    return render_template('admin_login.html')

# 2. 指揮中心 (受保護)
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect('/admin') # 沒登入就踢回門口
    return render_template('admin_dashboard.html')

# 3. 登出
@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect('/admin')

# 4. 取得所有資料 API (受保護，給指揮中心用)
@app.route('/api/admin/all_data')
def api_admin_all_data():
    if not session.get('logged_in'): 
        return jsonify([]) # 沒登入回傳空陣列
    
    try:
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
                'area': row[3],
                'note': row[4],
                'image_url': row[5],
                'nickname': row[6],
                'created_at': str(row[7])
            })
        return jsonify(locations)
    except Exception:
        return jsonify([])

# 5. 刪除資料 API (受保護)
@app.route('/api/delete', methods=['POST'])
def api_delete():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': '權限不足'})
    
    item_id = request.form.get('id')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM land_gods WHERE id = %s', (item_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# ================= 一般 API 邏輯 =================

# 公開的地點資料 API (給地圖和影像庫用)
@app.route('/api/locations')
def get_locations():
    try:
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
                'area': row[3],
                'note': row[4],
                'image_url': row[5],
                'nickname': row[6],
                'created_at': str(row[7])
            })
        return jsonify(locations)
    except Exception:
        return jsonify([])

# 上傳功能
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template('upload.html')
    
    init_db()

    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': '沒有檔案'})
    
    file = request.files['photo']
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    note = request.form.get('note')
    nickname = request.form.get('nickname')
    
    if file and lat and lng:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # 重複檢查
            cur.execute("SELECT lat, lng FROM land_gods")
            rows = cur.fetchall()
            for row in rows:
                if haversine(float(lng), float(lat), row[1], row[0]) < -1: 
                    conn.close()
                    return jsonify({'status': 'pending', 'message': '地點重複'})
            
            detected_area = get_location_name(lat, lng)

            # Cloudinary 上傳
            upload_result = cloudinary.uploader.upload(
                file,
                context={
                    "custom": {
                        "nickname": nickname,
                        "area": detected_area,
                        "caption": note,
                        "lat": lat,
                        "lng": lng
                    }
                }
            )
            image_url = upload_result['secure_url']

            # 寫入 DB
            cur.execute("INSERT INTO land_gods (image_url, lat, lng, note, nickname, area) VALUES (%s, %s, %s, %s, %s, %s)",
                        (image_url, float(lat), float(lng), note, nickname, detected_area))
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({'status': 'success', 'url': image_url, 'area': detected_area})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({'status': 'error', 'message': '資料不完整'})

@app.route('/api/leaderboard_data')
def leaderboard_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT nickname, COUNT(*) as count FROM land_gods GROUP BY nickname ORDER BY count DESC LIMIT 10")
        user_rows = cur.fetchall()
        cur.execute("SELECT area, COUNT(*) as count FROM land_gods GROUP BY area ORDER BY count DESC LIMIT 10")
        area_rows = cur.fetchall()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'by_user': [{'name': r[0] or '熱心串友', 'count': r[1]} for r in user_rows],
            'by_area': [{'name': r[0] or '未知區域', 'count': r[1]} for r in area_rows]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
