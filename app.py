import os
import uuid
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError('.env에 SECRET_KEY를 설정해 주세요.')
app.config['MAX_CONTENT_LENGTH'] = 26 * 1024 * 1024
UPLOAD_DIR = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
def db():
    return mysql.connector.connect(host=os.getenv('DB_HOST'), port=int(os.getenv('DB_PORT', 3306)), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'))
def read(sql, params=(), one=False):
    conn = db()
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()
def write(sql, params=()):
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.lastrowid
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def logged_in():
    return 'user_id' in session
def item_input():
    title = request.form.get('title', '').strip()
    category = request.form.get('category_id', '')
    description = request.form.get('description', '').strip()
    memo = request.form.get('sharing_memo', '').strip()
    valid = {str(c['category_id']) for c in read('SELECT category_id FROM categories')}
    if not title or not description or category not in valid: raise ValueError('필수 항목을 올바르게 입력해 주세요.')
    if len(title) > 100 or len(description) > 500 or len(memo) > 255: raise ValueError('입력 가능한 글자 수를 초과했습니다.')
    files = [f for f in request.files.getlist('images') if f.filename]
    if len(files) > 5: raise ValueError('사진은 최대 5장까지 등록할 수 있습니다.')
    images = []
    for f in files:
        data = f.read(5 * 1024 * 1024 + 1)
        ext = f.filename.rsplit('.', 1)[-1].lower()
        valid_image = ((ext in ('jpg', 'jpeg') and data.startswith(b'\xff\xd8\xff')) or
            (ext == 'png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or
            (ext == 'webp' and data.startswith(b'RIFF') and data[8:12] == b'WEBP'))
        if not valid_image or len(data) > 5 * 1024 * 1024:
            raise ValueError('사진은 JPG, PNG, WEBP 형식이며 장당 5MB 이하여야 합니다.')
        images.append((data, 'jpg' if ext == 'jpeg' else ext))
    return (title, category, description, memo), images
def save_images(cur, item_id, images, saved):
    for order, (data, ext) in enumerate(images, 1):
        name = uuid.uuid4().hex + '.' + ext
        path = os.path.join(UPLOAD_DIR, name)
        with open(path, 'wb') as f:
            f.write(data)
        saved.append('uploads/' + name)
        cur.execute('INSERT INTO item_images (item_id,image_path,image_order) VALUES (%s,%s,%s)',
            (item_id, 'uploads/' + name, order))
def remove_images(paths):
    for name in paths:
        path = os.path.join(UPLOAD_DIR, os.path.basename(name))
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            app.logger.exception('이미지 파일 삭제 실패')
@app.route('/')
def home():
    category = request.args.get('category', 'all')
    names = {'book': '도서', 'electronics': '전자기기', 'stationery': '학용품',
             'living': '생활용품', 'clothes': '의류/잡화'}
    sql = '''SELECT i.*,u.nickname,c.category_name,
        (SELECT image_path FROM item_images WHERE item_id=i.item_id ORDER BY image_order LIMIT 1) image_path
        FROM items i JOIN users u ON i.user_id=u.user_id JOIN categories c ON i.category_id=c.category_id'''
    params = ()
    if category in names:
        sql += ' WHERE c.category_name=%s'
        params = (names[category],)
    items = read(sql + ' ORDER BY i.created_at DESC,i.item_id DESC', params)
    return render_template('index.html', items=items, selected_category=category)
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET': return render_template('signup.html')
    nickname = request.form.get('nickname', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm = request.form.get('password_confirm', '')
    if not all((nickname, email, password, confirm)):
        error = '모든 항목을 입력해 주세요.'
    elif not email.endswith('@e-mirim.hs.kr'):
        error = '학교 이메일로만 가입할 수 있습니다.'
    elif len(password) < 8 or password != confirm:
        error = '비밀번호는 8자 이상이며 확인란과 일치해야 합니다.'
    else:
        error = None
    if error:
        return render_template('signup.html', error=error)
    try:
        write('INSERT INTO users (nickname,email,password_hash) VALUES (%s,%s,%s)',
            (nickname, email, generate_password_hash(password)))
    except mysql.connector.IntegrityError:
        return render_template('signup.html', error='이미 가입된 이메일입니다.')
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET': return render_template('login.html')
    user = read('SELECT * FROM users WHERE email=%s',
        (request.form.get('email', '').strip().lower(),), one=True)
    if user and user['password_hash'] and check_password_hash(user['password_hash'], request.form.get('password', '')):
        session.clear()
        session.update(user_id=user['user_id'], nickname=user['nickname'])
        return redirect(url_for('home'))
    return render_template('login.html', error='이메일 또는 비밀번호가 올바르지 않습니다.')
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))
@app.route('/add', methods=['GET', 'POST'])
def add():
    if not logged_in(): return redirect(url_for('login'))
    categories = read('SELECT * FROM categories ORDER BY category_id')
    if request.method == 'GET':
        return render_template('add.html', categories=categories)
    try:
        values, images = item_input()
    except ValueError as e:
        return render_template('add.html', categories=categories, form_data=dict(request.form), error=str(e))
    conn, saved = db(), []
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO items (user_id,category_id,title,description,sharing_memo,status)
                VALUES (%s,%s,%s,%s,%s,'나눔중')''',
                (session['user_id'], values[1], values[0], values[2], values[3]))
            save_images(cur, cur.lastrowid, images, saved)
        conn.commit()
    except Exception:
        conn.rollback()
        remove_images(saved)
        app.logger.exception('물품 등록 실패')
        return render_template('add.html', categories=categories,
            form_data=dict(request.form), error='등록 중 오류가 발생했습니다.'), 500
    finally:
        conn.close()
    return redirect(url_for('home'))
@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = read('''SELECT i.*,u.nickname,c.category_name FROM items i
        JOIN users u ON i.user_id=u.user_id JOIN categories c ON i.category_id=c.category_id
        WHERE i.item_id=%s''', (item_id,), one=True)
    if not item: return '존재하지 않는 물품입니다.', 404
    images = read('SELECT image_path FROM item_images WHERE item_id=%s ORDER BY image_order', (item_id,))
    application_status = None
    if logged_in():
        application = read('SELECT status FROM applications WHERE item_id=%s AND user_id=%s',
            (item_id, session['user_id']), one=True)
        application_status = application['status'] if application else None
    applicants = []
    if session.get('user_id') == item['user_id']:
        applicants = read('''SELECT a.*,u.nickname FROM applications a JOIN users u ON a.user_id=u.user_id
            WHERE a.item_id=%s ORDER BY a.created_at DESC''', (item_id,))
    return render_template('detail.html', item=item, images=images,
        application_status=application_status, applicants=applicants)
@app.route('/apply/<int:item_id>', methods=['POST'])
def apply(item_id):
    if not logged_in(): return redirect(url_for('login'))
    item = read('SELECT user_id,status FROM items WHERE item_id=%s', (item_id,), one=True)
    if not item: return '존재하지 않는 물품입니다.', 404
    if item['user_id'] == session['user_id'] or item['status'] != '나눔중':
        flash('신청할 수 없는 물품입니다.')
    else:
        try:
            write("INSERT INTO applications (item_id,user_id,status) VALUES (%s,%s,'대기')",
                (item_id, session['user_id']))
            flash('나눔 신청이 완료되었습니다!')
        except mysql.connector.IntegrityError:
            flash('이미 신청한 물품입니다.')
    return redirect(url_for('item_detail', item_id=item_id))
def decide(application_id, accept):
    conn = db()
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute('SELECT item_id FROM applications WHERE application_id=%s', (application_id,))
            application = cur.fetchone()
            if not application:
                return '존재하지 않는 신청입니다.', 404
            item_id = application['item_id']
            cur.execute('SELECT user_id,status FROM items WHERE item_id=%s FOR UPDATE', (item_id,))
            item = cur.fetchone()
            if not item or item['user_id'] != session['user_id']:
                return '권한이 없습니다.', 403
            cur.execute('SELECT status FROM applications WHERE application_id=%s FOR UPDATE', (application_id,))
            current = cur.fetchone()
            if item['status'] != '나눔중' or not current or current['status'] != '대기':
                flash('이미 처리된 신청입니다.')
            else:
                cur.execute('UPDATE applications SET status=%s WHERE application_id=%s',
                    ('수락' if accept else '거절', application_id))
                if accept:
                    cur.execute("UPDATE applications SET status='거절' WHERE item_id=%s AND status='대기'", (item_id,))
                    cur.execute("UPDATE items SET status='나눔완료' WHERE item_id=%s", (item_id,))
                conn.commit()
                flash('신청을 수락했습니다.' if accept else '신청을 거절했습니다.')
        return redirect(url_for('item_detail', item_id=item_id))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
@app.route('/accept/<int:application_id>', methods=['POST'])
def accept_application(application_id):
    return redirect(url_for('login')) if not logged_in() else decide(application_id, True)
@app.route('/reject/<int:application_id>', methods=['POST'])
def reject_application(application_id):
    return redirect(url_for('login')) if not logged_in() else decide(application_id, False)
@app.route('/mypage')
def mypage():
    if not logged_in(): return redirect(url_for('login'))
    user_id = session['user_id']
    tab = request.args.get('tab', 'registered')
    if tab not in ('registered', 'applied'):
        tab = 'registered'
    registered_items = read('''SELECT i.*,c.category_name,
        (SELECT image_path FROM item_images WHERE item_id=i.item_id ORDER BY image_order LIMIT 1) image_path,
        (SELECT COUNT(*) FROM applications WHERE item_id=i.item_id) applicant_count
        FROM items i JOIN categories c ON i.category_id=c.category_id
        WHERE i.user_id=%s ORDER BY i.created_at DESC''', (user_id,))
    applied_items = read('''SELECT i.item_id,i.title,i.status item_status,c.category_name,u.nickname,
        a.application_id,a.status application_status,a.created_at applied_at,
        (SELECT image_path FROM item_images WHERE item_id=i.item_id ORDER BY image_order LIMIT 1) image_path
        FROM applications a JOIN items i ON a.item_id=i.item_id
        JOIN users u ON i.user_id=u.user_id JOIN categories c ON i.category_id=c.category_id
        WHERE a.user_id=%s ORDER BY a.created_at DESC''', (user_id,))
    return render_template('mypage.html', tab=tab,
        registered_items=registered_items, applied_items=applied_items)
@app.route('/cancel/<int:application_id>', methods=['POST'])
def cancel_application(application_id):
    if not logged_in(): return redirect(url_for('login'))
    application = read('SELECT user_id,status FROM applications WHERE application_id=%s',
        (application_id,), one=True)
    if application and application['user_id'] == session['user_id'] and application['status'] == '대기':
        write("DELETE FROM applications WHERE application_id=%s AND user_id=%s AND status='대기'",
            (application_id, session['user_id']))
        flash('신청이 취소되었습니다.')
    else:
        flash('취소할 수 없는 신청입니다.')
    return redirect(url_for('mypage', tab='applied'))
@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if not logged_in(): return redirect(url_for('login'))
    item = read('SELECT * FROM items WHERE item_id=%s', (item_id,), one=True)
    if not item: return '존재하지 않는 물품입니다.', 404
    if item['user_id'] != session['user_id']:
        return '수정 권한이 없습니다.', 403
    if item['status'] != '나눔중':
        flash('나눔이 완료된 물품은 수정할 수 없습니다.')
        return redirect(url_for('item_detail', item_id=item_id))
    if request.method == 'GET':
        return render_template('edit.html', item=item,
            categories=read('SELECT * FROM categories ORDER BY category_id'),
            images=read('SELECT image_path FROM item_images WHERE item_id=%s ORDER BY image_order', (item_id,)))
    try:
        values, images = item_input()
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('edit_item', item_id=item_id))
    conn, saved, old = db(), [], []
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute('SELECT user_id,status FROM items WHERE item_id=%s FOR UPDATE', (item_id,))
            current = cur.fetchone()
            if not current or current['user_id'] != session['user_id']:
                return '수정 권한이 없습니다.', 403
            if current['status'] != '나눔중':
                flash('나눔이 완료된 물품은 수정할 수 없습니다.')
                return redirect(url_for('item_detail', item_id=item_id))
            cur.execute('''UPDATE items SET title=%s,category_id=%s,description=%s,sharing_memo=%s
                WHERE item_id=%s''', (*values, item_id))
            if images:
                cur.execute('SELECT image_path FROM item_images WHERE item_id=%s', (item_id,))
                old = [row['image_path'] for row in cur.fetchall()]
                cur.execute('DELETE FROM item_images WHERE item_id=%s', (item_id,))
                save_images(cur, item_id, images, saved)
        conn.commit()
    except Exception:
        conn.rollback()
        remove_images(saved)
        app.logger.exception('상품 수정 실패')
        flash('상품 수정 중 오류가 발생했습니다.')
        return redirect(url_for('edit_item', item_id=item_id))
    finally:
        conn.close()
    remove_images(old)
    flash('상품이 수정되었습니다!')
    return redirect(url_for('item_detail', item_id=item_id))
@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if not logged_in(): return redirect(url_for('login'))
    conn, images = db(), []
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute('SELECT user_id,status FROM items WHERE item_id=%s FOR UPDATE', (item_id,))
            item = cur.fetchone()
            if not item:
                return '존재하지 않는 물품입니다.', 404
            if item['user_id'] != session['user_id']:
                return '삭제 권한이 없습니다.', 403
            if item['status'] != '나눔중':
                flash('나눔이 완료된 물품은 삭제할 수 없습니다.')
                return redirect(url_for('item_detail', item_id=item_id))
            cur.execute('SELECT image_path FROM item_images WHERE item_id=%s', (item_id,))
            images = [row['image_path'] for row in cur.fetchall()]
            for table in ('applications', 'item_images'):
                cur.execute(f'DELETE FROM {table} WHERE item_id=%s', (item_id,))
            cur.execute('DELETE FROM items WHERE item_id=%s', (item_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        app.logger.exception('상품 삭제 실패')
        flash('상품 삭제 중 오류가 발생했습니다.')
        return redirect(url_for('item_detail', item_id=item_id))
    finally:
        conn.close()
    remove_images(images)
    flash('상품이 삭제되었습니다!')
    return redirect(url_for('mypage'))
@app.route('/notice')
def notice():
    return render_template('notice.html')
@app.errorhandler(RequestEntityTooLarge)
def file_too_large(error):
    return '사진 용량이 너무 큽니다.', 413
if __name__ == '__main__':
    app.run(debug=True)
