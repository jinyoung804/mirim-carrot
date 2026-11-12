import os

import mysql.connector

from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ==========================================
# 1. Flask 설정
# ==========================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "SECRET_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요."
    )


# ==========================================
# 2. MySQL 연결
# ==========================================

def get_db_connection():

    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# ==========================================
# 3. 메인 페이지
# ==========================================

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

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        sql = """
            SELECT
                items.item_id,
                items.title,
                items.description,
                items.status,
                items.created_at,
                users.nickname,
                categories.category_name

            FROM items

            JOIN users
                ON items.user_id = users.user_id

            JOIN categories
                ON items.category_id = categories.category_id
        """

        params = []

        # 카테고리별 조회
        if category in category_map:

            sql += """
                WHERE categories.category_name = %s
            """

            params.append(category_map[category])

        sql += """
            ORDER BY
                items.created_at DESC,
                items.item_id DESC
        """

        cursor.execute(sql, tuple(params))

        items = cursor.fetchall()

    finally:

        cursor.close()
        conn.close()

    return render_template(
        "index.html",
        items=items,
        selected_category=category
    )


# ==========================================
# 4. 회원가입
# ==========================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        nickname = request.form.get("nickname", "").strip()

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        password_confirm = request.form.get(
            "password_confirm", ""
        )

        # 필수 항목 검사
        if not nickname or not email or not password or not password_confirm:

            return render_template(
                "signup.html",
                error="모든 항목을 입력해 주세요."
            )

        # 학교 이메일 검사
        if not email.endswith("@e-mirim.hs.kr"):

            return render_template(
                "signup.html",
                error="학교 이메일(@e-mirim.hs.kr)로만 가입할 수 있습니다."
            )

        # 비밀번호 길이 검사
        if len(password) < 8:

            return render_template(
                "signup.html",
                error="비밀번호는 8자 이상 입력해 주세요."
            )

        # 비밀번호 일치 검사
        if password != password_confirm:

            return render_template(
                "signup.html",
                error="비밀번호가 일치하지 않습니다."
            )

        # 비밀번호 암호화
        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users (
                    nickname,
                    email,
                    password_hash
                )
                VALUES (%s, %s, %s)
                """,
                (
                    nickname,
                    email,
                    password_hash
                )
            )

            conn.commit()

        except mysql.connector.IntegrityError:

            conn.rollback()

            return render_template(
                "signup.html",
                error="이미 가입된 이메일입니다."
            )

        finally:

            cursor.close()
            conn.close()

        return redirect(url_for("login"))

    return render_template("signup.html")


# ==========================================
# 5. 로그인
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT
                    user_id,
                    nickname,
                    email,
                    password_hash

                FROM users

                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

        finally:

            cursor.close()
            conn.close()

        # 로그인 성공
        if (
            user
            and user["password_hash"]
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):

            session.clear()

            session["user_id"] = user["user_id"]

            session["nickname"] = user["nickname"]

            return redirect(url_for("home"))

        # 로그인 실패
        return render_template(
            "login.html",
            error="이메일 또는 비밀번호가 올바르지 않습니다."
        )

    return render_template("login.html")


# ==========================================
# 6. 로그아웃
# ==========================================

@app.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return redirect(url_for("home"))


# ==========================================
# 7. 나눔 등록
# ==========================================

@app.route("/add", methods=["GET", "POST"])
def add():

    # 로그인 여부 확인
    if not session.get("user_id"):

        return redirect(url_for("login"))

    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)

    try:

        # 카테고리 목록 가져오기
        cursor.execute(
            """
            SELECT
                category_id,
                category_name

            FROM categories

            ORDER BY category_id
            """
        )

        categories = cursor.fetchall()

        # 등록 버튼을 눌렀을 때
        if request.method == "POST":

            title = request.form.get("title", "").strip()

            category_id = request.form.get(
                "category_id", ""
            ).strip()

            description = request.form.get(
                "description", ""
            ).strip()

            
            status =  "나눔중"
            

            form_data = {
                "title": title,
                "category_id": category_id,
                "description": description,
                "status": status
            }

            # 필수 항목 검사
            if not title or not category_id or not description:

                return render_template(
                    "add.html",
                    categories=categories,
                    form_data=form_data,
                    error="필수 항목을 모두 입력해 주세요."
                )

            # 글자 수 검사
            if len(title) > 100 or len(description) > 500:

                return render_template(
                    "add.html",
                    categories=categories,
                    form_data=form_data,
                    error="입력 가능한 글자 수를 초과했습니다."
                )

            # 나눔 상태 검사
            if status not in ["나눔중", "나눔완료"]:

                return render_template(
                    "add.html",
                    categories=categories,
                    form_data=form_data,
                    error="올바른 나눔 상태를 선택해 주세요."
                )

            # 카테고리 검사
            category_exists = any(
                str(category["category_id"]) == category_id
                for category in categories
            )

            if not category_exists:

                return render_template(
                    "add.html",
                    categories=categories,
                    form_data=form_data,
                    error="올바른 카테고리를 선택해 주세요."
                )

            # MySQL에 물품 저장
            cursor.execute(
                """
                INSERT INTO items (
                    user_id,
                    category_id,
                    title,
                    description,
                    status
                )

                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    int(category_id),
                    title,
                    description,
                    status
                )
            )

            conn.commit()

            # 등록 완료 후 메인 페이지 이동
            return redirect(url_for("home"))

        # 등록 화면 표시
        return render_template(
            "add.html",
            categories=categories
        )

    except Exception:

        conn.rollback()

        app.logger.exception("나눔 등록 오류")

        return render_template(
            "add.html",
            categories=categories if "categories" in locals() else [],
            form_data=request.form if request.method == "POST" else None,
            error="등록 중 오류가 발생했습니다."
        ), 500

    finally:

        cursor.close()
        conn.close()


# ==========================================
# 8. Flask 실행
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)