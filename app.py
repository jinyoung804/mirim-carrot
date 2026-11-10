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
# 1. 환경 변수 및 Flask 설정
# ==========================================

# .env 파일에 저장된 환경 변수 불러오기
load_dotenv()

# Flask 애플리케이션 생성
app = Flask(__name__)

# 로그인 세션을 보호하기 위한 비밀키
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")


# ==========================================
# 2. MySQL 데이터베이스 연결
# ==========================================

def get_db_connection():
    """
    .env 파일에 저장된 정보를 이용해
    MySQL 데이터베이스에 연결하는 함수
    """

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
    """
    MySQL에 저장된 나눔 물품을 조회하고
    메인 페이지에 전달하는 함수
    """

    # 데이터베이스 연결
    conn = get_db_connection()

    # 조회 결과를 딕셔너리 형태로 가져오기
    cursor = conn.cursor(dictionary=True)

    try:
        # 물품, 회원, 카테고리 테이블을 연결하여 조회
        sql = """
            SELECT
                items.item_id,
                items.title,
                items.description,
                items.status,
                users.nickname,
                categories.category_name
            FROM items
            JOIN users
                ON items.user_id = users.user_id
            JOIN categories
                ON items.category_id = categories.category_id
            ORDER BY
                items.created_at DESC,
                items.item_id DESC
        """

        # SQL 실행
        cursor.execute(sql)

        # 조회된 물품 목록 저장
        items = cursor.fetchall()

    finally:
        # 데이터베이스 연결 종료
        cursor.close()
        conn.close()

    # 조회된 물품 정보를 HTML로 전달
    return render_template("index.html", items=items)


# ==========================================
# 4. 회원가입
# ==========================================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    GET  : 회원가입 화면 표시
    POST : 회원 정보를 MySQL에 저장
    """

    # 회원가입 버튼을 눌렀을 때
    if request.method == "POST":

        # HTML 입력창에서 회원 정보 가져오기
        nickname = request.form.get("nickname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # ----------------------------------
        # 4-1. 필수 입력값 확인
        # ----------------------------------

        if not nickname or not email or not password or not password_confirm:
            return render_template(
                "signup.html",
                error="모든 항목을 입력해 주세요."
            )

        # ----------------------------------
        # 4-2. 학교 이메일 확인
        # ----------------------------------

        # 미림마이스터고 학교 이메일만 허용
        if not email.endswith("@e-mirim.hs.kr"):
            return render_template(
                "signup.html",
                error="학교 이메일(@e-mirim.hs.kr)로만 가입할 수 있습니다."
            )

        # ----------------------------------
        # 4-3. 비밀번호 확인
        # ----------------------------------

        # 비밀번호는 최소 8자 이상
        if len(password) < 8:
            return render_template(
                "signup.html",
                error="비밀번호는 8자 이상 입력해 주세요."
            )

        # 비밀번호와 비밀번호 확인이 같은지 검사
        if password != password_confirm:
            return render_template(
                "signup.html",
                error="비밀번호가 일치하지 않습니다."
            )

        # ----------------------------------
        # 4-4. 비밀번호 해시 처리
        # ----------------------------------

        # 비밀번호를 그대로 저장하지 않고
        # 안전하게 해시 처리하여 저장
        password_hash = generate_password_hash(password)

        # ----------------------------------
        # 4-5. MySQL에 회원 정보 저장
        # ----------------------------------

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            sql = """
                INSERT INTO users (
                    nickname,
                    email,
                    password_hash
                )
                VALUES (%s, %s, %s)
            """

            cursor.execute(
                sql,
                (nickname, email, password_hash)
            )

            # 데이터베이스에 변경 사항 저장
            conn.commit()

        except mysql.connector.IntegrityError:

            # 오류 발생 시 저장 취소
            conn.rollback()

            return render_template(
                "signup.html",
                error="이미 가입된 이메일입니다."
            )

        finally:
            # 데이터베이스 연결 종료
            cursor.close()
            conn.close()

        # 회원가입 성공 시 로그인 페이지로 이동
        return redirect(url_for("login"))

    # GET 요청이면 회원가입 화면 표시
    return render_template("signup.html")


# ==========================================
# 5. 로그인
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    GET  : 로그인 화면 표시
    POST : 이메일과 비밀번호 확인
    """

    # 로그인 버튼을 눌렀을 때
    if request.method == "POST":

        # 입력한 이메일과 비밀번호 가져오기
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # ----------------------------------
        # 5-1. 회원 정보 조회
        # ----------------------------------

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            sql = """
                SELECT
                    user_id,
                    nickname,
                    email,
                    password_hash
                FROM users
                WHERE email = %s
            """

            cursor.execute(sql, (email,))

            # 입력한 이메일에 해당하는 회원 조회
            user = cursor.fetchone()

        finally:
            cursor.close()
            conn.close()

        # ----------------------------------
        # 5-2. 비밀번호 검증
        # ----------------------------------

        # 회원이 존재하고 비밀번호가 일치하는 경우
        if (
            user
            and user["password_hash"]
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):

            # 기존 세션 초기화
            session.clear()

            # 로그인한 회원 정보 저장
            session["user_id"] = user["user_id"]
            session["nickname"] = user["nickname"]

            # 로그인 성공 시 메인 페이지로 이동
            return redirect(url_for("home"))

        # 로그인 실패 시 오류 메시지 표시
        return render_template(
            "login.html",
            error="이메일 또는 비밀번호가 올바르지 않습니다."
        )

    # GET 요청이면 로그인 화면 표시
    return render_template("login.html")


# ==========================================
# 6. 로그아웃
# ==========================================

@app.route("/logout", methods=["POST"])
def logout():
    """
    현재 로그인한 회원의 세션을 삭제하여
    로그아웃 처리하는 함수
    """

    # 로그인 세션 정보 삭제
    session.clear()

    # 로그아웃 후 메인 페이지로 이동
    return redirect(url_for("home"))


# ==========================================
# 7. Flask 서버 실행
# ==========================================

if __name__ == "__main__":

    # 개발용 Flask 서버 실행
    app.run(debug=True)