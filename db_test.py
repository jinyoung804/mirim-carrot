import os

import mysql.connector
from dotenv import load_dotenv

# .env 파일에 저장된 환경변수 불러오기
load_dotenv()

try:
    # MySQL 데이터베이스 연결
    conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

    print("MySQL 연결 성공!")

    # SQL 실행
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items")

    # 조회 결과 가져오기
    items = cursor.fetchall()

    print("등록된 물품 목록:")

    for item in items:
        print(item)

    cursor.close()
    conn.close()

except mysql.connector.Error as error:
    print("MySQL 연결 오류:", error)