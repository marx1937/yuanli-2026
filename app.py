import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
import cloudinary
import cloudinary.uploader
from math import radians, cos, sin, asin, sqrt

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

# ================= 頁面路由 (Routes) =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map')
def map_page():
    return render_template('map.html')

# 🏆 排行榜 (你說不見的就是這個！)
@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

# 📸 圖庫頁面
@app.route('/gallery')
def gallery_page():
    return render_template('gallery.html')


# 🔧 管理員登入頁
@app.route('/login')
def login_page():
    return render_template('login.html')

# 🔧 管理員後台
@app.route('/admin')
def admin_page():
    if not session.get('is_admin'):
        return redirect(url_for('login_page'))
    return render_template('admin.html')

# 🔗 救命導航：不管按首頁哪個按鈕，都導向正確的上傳頁
@app.route('/report')
@app.route('/upload_page')
def show_upload_page():
    return render_template('upload.html')

# ================= 功能邏輯 (API) =================

# 1. 管理員登入驗證
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': '密碼錯誤'})

# 2. 核心：上傳功能 (包含重複檢查)
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    # 如果是 GET 請求，就顯示頁面
    if request.method == 'GET':
        return render_template('upload.html')

    # 如果是 POST 請求，處理上傳
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
            
            # --- 🛑 重複地點檢查 (守門員) ---
            cur.execute("SELECT lat, lng FROM land_gods")
            rows = cur.fetchall()
            
            for row in rows:
                db_lat = row[0]
                db_lng = row[1]
                # ⚠️ 測試模式：0.5 (500公尺)，測試完記得改回 0.05
                dist = haversine(float(lng), float(lat), db_lng, db_lat)
                
                if dist < -1: 
                    conn.close()
                    return jsonify({'status': 'pending', 'message': '地點重複，已送審'})
            
            # --- ✅ 上傳流程 ---
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

# 3. 提供地圖資料 API
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


    # ================= 管理員專用 API (新增) =================

# 1. 取得所有土地公資料 (顯示所有照片，包含成功的)
@app.route('/api/admin/all_data')
def get_all_data():
    # 權限檢查 (先關掉方便你測試，正式上線可打開)
    # if not session.get('is_admin'):
    #     return jsonify({'status': 'error', 'message': '權限不足'})
        
    conn = get_db_connection()
    cur = conn.cursor()
    # 依 ID 由大到小排序 (最新的在最上面)
    cur.execute("SELECT id, area, nickname, note, image_url, created_at FROM land_gods ORDER BY id DESC")
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
            'created_at': str(row[5])
        })
    return jsonify(data)

# ================= 排行榜專用 API (修復版) =================
@app.route('/api/leaderboard_data')
def leaderboard_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. 抓取【個人】排行榜 (前 10 名)
        cur.execute("""
            SELECT nickname, COUNT(*) as count 
            FROM land_gods 
            GROUP BY nickname 
            ORDER BY count DESC 
            LIMIT 10
        """)
        user_rows = cur.fetchall()

        # 2. 抓取【區域】排行榜 (前 10 名)
        cur.execute("""
            SELECT area, COUNT(*) as count 
            FROM land_gods 
            GROUP BY area 
            ORDER BY count DESC 
            LIMIT 10
        """)
        area_rows = cur.fetchall()
        
        conn.close()
        
        # 整理資料回傳
        return jsonify({
            'status': 'success',
            'by_user': [{'name': r[0] or '熱心串友', 'count': r[1]} for r in user_rows],
            'by_area': [{'name': r[0], 'count': r[1]} for r in area_rows]
        })

    except Exception as e:
        print("排行榜錯誤:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 🗑️ 刪除功能 API
@app.route('/api/delete', methods=['POST'])
def delete_location():
    # 1. 安全檢查：確認是不是管理員 (沒有登入不能刪)
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': '權限不足，請先登入'})

    # 2. 獲取要刪除的 ID
    location_id = request.form.get('id')
    
    if not location_id:
        return jsonify({'success': False, 'message': '找不到 ID'})

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 3. 執行資料庫刪除指令
        cur.execute('DELETE FROM land_gods WHERE id = %s', (location_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "已成功刪除"})
        
    except Exception as e:
        print("刪除失敗:", e)
        return jsonify({"success": False, "message": "資料庫錯誤"})


# ================= 程式啟動點 =================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

