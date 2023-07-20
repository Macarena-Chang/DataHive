CREATE DATABASE datadb;

USE datadb;

CREATE TABLE users (
    user_id int AUTO_INCREMENT PRIMARY KEY,
    username varchar(255) UNIQUE NOT NULL,
    full_name varchar(255) NOT NULL,
    email varchar(255) UNIQUE NOT NULL,
    hashed_password varchar(255) NOT NULL,
    disabled boolean DEFAULT FALSE
);

INSERT INTO users (username, full_name, email, hashed_password, disabled)
    VALUES ('macarena', 'Macarena Chang', 'macarena@mail.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', FALSE);

ALTER TABLE users
    ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;

CREATE TABLE files (
    file_id varchar(36) PRIMARY KEY,
    file_name varchar(255)
);

CREATE TABLE user_files (
    id int PRIMARY KEY AUTO_INCREMENT,
    user_id int,
    file_id varchar(36),
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (file_id) REFERENCES files (file_id)
);
