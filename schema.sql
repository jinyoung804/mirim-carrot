-- ============================================
-- 미림당근 데이터베이스
-- 학교 학생 간 무료 나눔 웹사이트
-- ============================================

CREATE DATABASE IF NOT EXISTS mirim_carrot
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE mirim_carrot;


-- ============================================
-- 1. 회원 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    user_id INT NOT NULL AUTO_INCREMENT,
    nickname VARCHAR(30) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) DEFAULT NULL,

    PRIMARY KEY (user_id),
    UNIQUE KEY uq_users_email (email)

) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;


-- ============================================
-- 2. 카테고리 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS categories (
    category_id INT NOT NULL AUTO_INCREMENT,
    category_name VARCHAR(30) NOT NULL,

    PRIMARY KEY (category_id),
    UNIQUE KEY uq_categories_name (category_name)

) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;


-- ============================================
-- 3. 나눔 물품 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS items (
    item_id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    category_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT DEFAULT NULL,
    status ENUM('나눔중', '나눔완료')
        NOT NULL DEFAULT '나눔중',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sharing_memo VARCHAR(255) DEFAULT NULL,

    PRIMARY KEY (item_id),

    CONSTRAINT fk_items_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_items_category
        FOREIGN KEY (category_id)
        REFERENCES categories(category_id)

) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;


-- ============================================
-- 4. 물품 이미지 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS item_images (
    image_id INT NOT NULL AUTO_INCREMENT,
    item_id INT NOT NULL,
    image_path VARCHAR(255) NOT NULL,
    image_order INT DEFAULT 1,

    PRIMARY KEY (image_id),

    CONSTRAINT fk_images_item
        FOREIGN KEY (item_id)
        REFERENCES items(item_id)
        ON DELETE CASCADE

) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;


-- ============================================
-- 5. 나눔 신청 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS applications (
    application_id INT NOT NULL AUTO_INCREMENT,
    item_id INT NOT NULL,
    user_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT '대기',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (application_id),

    -- 동일한 물품에 중복 신청 방지
    UNIQUE KEY uq_application (item_id, user_id),

    CONSTRAINT fk_applications_item
        FOREIGN KEY (item_id)
        REFERENCES items(item_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_applications_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE

) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;