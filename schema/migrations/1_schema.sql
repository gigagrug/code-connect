CREATE TABLE IF NOT EXISTS users (
	id INT AUTO_INCREMENT PRIMARY KEY,
	name VARCHAR(150),
	email VARCHAR(150) NOT NULL UNIQUE,
	password VARCHAR(255) NOT NULL,
	account_type INT NOT NULL,
	role INT NOT NULL DEFAULT 0,
	instructor_id INT NULL,
	FOREIGN KEY (instructor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS instructor_requests (
	id INT AUTO_INCREMENT PRIMARY KEY,
	student_id INT NOT NULL,
	instructor_id INT NOT NULL,
	status TINYINT DEFAULT 0,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
	FOREIGN KEY (instructor_id) REFERENCES users(id) ON DELETE CASCADE,
	UNIQUE KEY unique_pending_request (student_id, instructor_id)
);

CREATE TABLE IF NOT EXISTS projects (
	id INT AUTO_INCREMENT PRIMARY KEY,
	user_id INT,
	name VARCHAR(255) NOT NULL,
	description TEXT NOT NULL,
	status INT DEFAULT 0,
	project_link VARCHAR(255),
	github_link VARCHAR(255),
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teams (
	id INT AUTO_INCREMENT PRIMARY KEY,
	name VARCHAR(25) NOT NULL,
	user_id INT NOT NULL,
	project_id INT,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
	FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_members (
	team_id INT NOT NULL,
	user_id INT NOT NULL,
	PRIMARY KEY (team_id, user_id),
	FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
	id INT AUTO_INCREMENT PRIMARY KEY,
	project_id INT NOT NULL,
	user_id INT NOT NULL,
	message_text TEXT NOT NULL,
	timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- schema rollback

DROP TABLE chat_messages;

DROP TABLE team_members;

DROP TABLE teams;

DROP TABLE projects;

DROP TABLE instructor_requests;

DROP TABLE users;
