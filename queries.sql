CREATE DATABASE datadb;
USE datadb;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    disabled BOOLEAN DEFAULT FALSE
);

INSERT INTO users (username, full_name, email, hashed_password, disabled) 
VALUES ('macarena', 'Macarena Chang', 'macarena@mail.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', FALSE);


CREATE TABLE files (
    file_id VARCHAR(36) PRIMARY KEY,
    file_name VARCHAR(255)
);

CREATE TABLE user_files (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    file_id VARCHAR(36),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);