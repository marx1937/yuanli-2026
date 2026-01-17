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
app.secret_key = os.environ.get('SECRET_KEY', 'yuanli_secret_key')
ADMIN_PASSWORD = 'ytc@358'

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

# --- 距離計算 ---
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

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/admin')
def admin_page():
    if not session.get('is_admin'): return redirect(url_for('login_page'))
    return render_template('admin.html')

@app.route('/report')
@app.route('/upload_page')
def show_upload_page(): return render_template('upload.html')

# ================= API 邏輯 =================
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': '密碼錯誤'})

# 🔥 重點修改：上傳時把資料寫入雲端 (Context)
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template('upload.html')
    
    init_db() # 再次確保有表格

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

            # 🔥 上傳 Cloudinary + 寫入標籤 (關鍵!)
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
                'timestamp': str(row[7])
            })
        return jsonify(locations)
    except Exception:
        return jsonify([])

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

# 🚑 救援功能 (不需要改，它現在已經能讀取上面新增的標籤了)
@app.route('/api/admin/rescue_data')
def rescue_data_from_cloudinary():
    try:
        init_db()
        import cloudinary.api
        result = cloudinary.api.resources(
            type="upload", resource_type="image", max_results=500, context=True 
        )
        resources = result.get('resources', [])
        
        conn = get_db_connection()
        cur = conn.cursor()
        count = 0
        
        for res in resources:
            url = res['secure_url']
            cur.execute("SELECT id FROM land_gods WHERE image_url = %s", (url,))
            if not cur.fetchone():
                # 這裡會嘗試讀取我們新加的標籤
                context = res.get('context', {}).get('custom', {})
                cur.execute("""
                    INSERT INTO land_gods (image_url, nickname, note, lat, lng, area, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    url, 
                    context.get('nickname', '熱心串友'), # 舊照片沒標籤，就變熱心串友
                    context.get('caption', ''), 
                    float(context.get('lat', 0)), 
                    float(context.get('lng', 0)), 
                    context.get('area', '苑裡'), 
                    res['created_at']
                ))
                count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success', 'message': f'救援成功！恢復了 {count} 筆資料'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/delete', methods=['POST'])
def delete_location():
    if not session.get('is_admin'): return jsonify({'success': False})
    location_id = request.form.get('id')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM land_gods WHERE id = %s', (location_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception:
        return jsonify({"success": False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
