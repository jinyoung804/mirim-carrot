import os

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

app = Flask(__name__)


# MySQL 연결 함수
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# 메인 페이지
@app.route("/")
def home():
    conn = get_db_connection()

    cursor = conn.cursor(dictionary=True)

    sql = """
        SELECT
            items.item_id,
            items.title,
            items.description,
            items.status,
            users.nickname,
            categories.category_name
        FROM items
        JOIN users ON items.user_id = users.user_id
        JOIN categories ON items.category_id = categories.category_id
        ORDER BY items.created_at DESC, items.item_id DESC
    """

    cursor.execute(sql)

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("index.html", items=items)


if __name__ == "__main__":
    app.run(debug=True)