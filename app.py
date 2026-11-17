import os
import uuid
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge

# 1. 기본 설정
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(".env 파일에 SECRET_KEY를 설정해 주세요.")

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 26 * 1024 * 1024  # 요청 전체 최대 26MB


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# 2. 사진 파일의 실제 형식을 확인하는 함수
# 파일 이름만 믿지 않고 파일 앞부분의 특징을 확인한다.
def check_image_type(data):
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


# 3. 메인 페이지
@app.route("/")
def home():
    category = request.args.get("category", "all")
    category_map = {
        "book": "도서",
        "electronics": "전자기기",
        "stationery": "학용품",
        "living": "생활용품",
        "clothes": "의류/잡화"
    }

    sql = """
        SELECT i.item_id, i.title, i.description, i.status, i.created_at,
               u.nickname, c.category_name,
               (SELECT image_path FROM item_images
                WHERE item_id = i.item_id
                ORDER BY image_order LIMIT 1) AS image_path
        FROM items i
        JOIN users u ON i.user_id = u.user_id
        JOIN categories c ON i.category_id = c.category_id
    """
    params = []
    if category in category_map:
        sql += " WHERE c.category_name = %s"
        params.append(category_map[category])
    sql += " ORDER BY i.created_at DESC, i.item_id DESC"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, tuple(params))
        items = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("index.html", items=items, selected_category=category)


# 4. 회원가입
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    nickname = request.form.get("nickname", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm = request.form.get("password_confirm", "")

    if not nickname or not email or not password or not confirm:
        error = "모든 항목을 입력해 주세요."
    elif not email.endswith("@e-mirim.hs.kr"):
        error = "학교 이메일로만 가입할 수 있습니다."
    elif len(password) < 8:
        error = "비밀번호는 8자 이상 입력해 주세요."
    elif password != confirm:
        error = "비밀번호가 일치하지 않습니다."
    else:
        error = None

    if error:
        return render_template("signup.html", error=error)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = "INSERT INTO users (nickname, email, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(sql, (nickname, email, generate_password_hash(password)))
        conn.commit()
    except mysql.connector.IntegrityError:
        conn.rollback()
        return render_template("signup.html", error="이미 가입된 이메일입니다.")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("login"))


# 5. 로그인
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT user_id, nickname, password_hash FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
        session.clear()
        session["user_id"] = user["user_id"]
        session["nickname"] = user["nickname"]
        return redirect(url_for("home"))

    return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다.")


# 6. 로그아웃
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


# 7. 나눔 등록 + 사진 업로드
@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    saved_files = []
    categories = []

    try:
        cursor.execute("SELECT category_id, category_name FROM categories ORDER BY category_id")
        categories = cursor.fetchall()

        if request.method == "GET":
            return render_template("add.html", categories=categories)

        title = request.form.get("title", "").strip()
        category_id = request.form.get("category_id", "").strip()
        description = request.form.get("description", "").strip()
        images = request.files.getlist("images")
        images = [image for image in images if image.filename]
        form_data = {"title": title, "category_id": category_id, "description": description}

        # 입력값 검사
        error = None
        if not title or not category_id or not description:
            error = "필수 항목을 모두 입력해 주세요."
        elif len(title) > 100 or len(description) > 500:
            error = "입력 가능한 글자 수를 초과했습니다."
        elif len(images) > 5:
            error = "사진은 최대 5장까지 등록할 수 있습니다."
        else:
            category_found = False
            for category in categories:
                if str(category["category_id"]) == category_id:
                    category_found = True
                    break
            if not category_found:
                error = "올바른 카테고리를 선택해 주세요."

        # 사진은 1장당 최대 5MB, JPG/PNG/WEBP만 허용
        checked_images = []
        if not error:
            for image in images:
                data = image.read(5 * 1024 * 1024 + 1)
                if len(data) > 5 * 1024 * 1024:
                    error = "사진은 한 장당 5MB 이하여야 합니다."
                    break
                image_type = check_image_type(data)
                if image_type is None:
                    error = "JPG, PNG, WEBP 사진만 등록할 수 있습니다."
                    break
                checked_images.append((data, image_type))

        if error:
            return render_template("add.html", categories=categories,
                                   form_data=form_data, error=error)

        # 물품을 먼저 저장하고 새로 만들어진 item_id를 가져온다.
        cursor.execute("""
            INSERT INTO items (user_id, category_id, title, description, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (session["user_id"], int(category_id), title, description, "나눔중"))
        item_id = cursor.lastrowid

        # 사진을 저장하고 사진 경로를 DB에 기록한다.
        for number, (data, image_type) in enumerate(checked_images, start=1):
            filename = uuid.uuid4().hex + "." + image_type
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            with open(file_path, "wb") as file:
                file.write(data)
            saved_files.append(file_path)

            db_path = "uploads/" + filename
            cursor.execute("""
                INSERT INTO item_images (item_id, image_path, image_order)
                VALUES (%s, %s, %s)
            """, (item_id, db_path, number))

        conn.commit()
        return redirect(url_for("home"))

    except Exception:
        conn.rollback()
        # DB 저장에 실패하면 방금 저장한 사진도 삭제한다.
        for file_path in saved_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        app.logger.exception("나눔 등록 오류")
        return render_template("add.html", categories=categories,
                               form_data=request.form if request.method == "POST" else None,
                               error="등록 중 오류가 발생했습니다."), 500
    finally:
        cursor.close()
        conn.close()


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(error):
    return "업로드 용량이 너무 큽니다. 사진은 한 장당 5MB 이하로 등록해 주세요.", 413
# 물품 상세 페이지
@app.route("/item/<int:item_id>")
def item_detail(item_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 물품 정보 가져오기
        cursor.execute("""
            SELECT
                items.item_id,
                items.user_id,
                items.title,
                items.description,
                items.status,
                items.created_at,
                users.nickname,
                categories.category_name
            FROM items
            JOIN users ON items.user_id = users.user_id
            JOIN categories ON items.category_id = categories.category_id
            WHERE items.item_id = %s
        """, (item_id,))

        item = cursor.fetchone()

        # 해당 물품이 없을 때
        if not item:
            return "존재하지 않는 물품입니다.", 404

        # 물품 사진 가져오기
        cursor.execute("""
            SELECT image_path
            FROM item_images
            WHERE item_id = %s
            ORDER BY image_order
        """, (item_id,))

        images = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    return render_template(
        "detail.html",
        item=item,
        images=images
    )

if __name__ == "__main__":
    app.run(debug=True)
