from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
import cloudinary
import cloudinary.uploader
import os
import psycopg2

app = Flask(__name__)

# --- 設定區 ---
# 設定加密鑰匙 (這是 Session 運作需要的)
app.secret_key = os.environ.get('SECRET_KEY', 'yuanli_secret_key')
# 設定管理員密碼 (從環境變數抓，如果沒設預設是 1234)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '1234')

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
    except Exception as e:
        print("資料庫錯誤:", e)

init_db()

# ================= 路由區 =================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/report')
def report_page():
    return render_template('upload.html')

@app.route('/map')
def map_page():
    return render_template('map.html')

@app.route('/welcome.jpg')
def welcome_image():
    return send_from_directory('.', 'welcome.jpg')

# --- 🔒 登入系統 ---

# 1. 登入頁面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True  # 發給通行證
            return redirect(url_for('admin_page'))
        else:
            return render_template('login.html', error="密碼錯誤，只有大哥能進來！")
    return render_template('login.html')

# 2. 登出
@app.route('/logout')
def logout():
    session.pop('is_admin', None) # 撕掉通行證
    return redirect(url_for('home'))

# 3. 管理後台 (有加保全檢查)
@app.route('/admin')
def admin_page():
    # 檢查有沒有通行證
    if not session.get('is_admin'):
        return redirect(url_for('login')) # 沒票就踢去登入頁
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, nickname, area, note, image_url, created_at FROM land_gods ORDER BY created_at DESC;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin.html', rows=rows)

# 4. 刪除功能 (也有保全)
@app.route('/delete/<int:id>')
def delete_post(id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM land_gods WHERE id = %s', (id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("刪除失敗:", e)
    
    return redirect(url_for('admin_page'))

# 3.5 圖庫頁 (新增這段)
@app.route('/gallery')
def gallery_page():
    conn = get_db_connection()
    cur = conn.cursor()
    # 撈出所有資料，按照時間新到舊排序
    cur.execute('SELECT image_url, nickname, area, note, created_at FROM land_gods ORDER BY created_at DESC;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('gallery.html', rows=rows)

# --- API 區 ---

@app.route('/api/rank')
def get_rank():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT nickname, COUNT(*) as count FROM land_gods GROUP BY nickname ORDER BY count DESC LIMIT 5;')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        rank_data = [{'name': r[0] if r[0] else "熱心串友", 'count': r[1]} for r in rows]
        return jsonify(rank_data)
    except: return jsonify([])

@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT image_url, lat, lng, note, nickname, area, created_at FROM land_gods;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    data = [{'image_url':r[0], 'lat':r[1], 'lng':r[2], 'note':r[3], 'nickname':r[4], 'area':r[5], 'created_at':str(r[6])} for r in rows]
    return jsonify(data)

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
        cur.execute('INSERT INTO land_gods (image_url, lat, lng, note, nickname, area) VALUES (%s, %s, %s, %s, %s, %s)', (image_url, lat, lng, note, nickname, area))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success', 'url': image_url})
    return jsonify({'status': 'error'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
