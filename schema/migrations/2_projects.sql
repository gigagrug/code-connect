CREATE TABLE IF NOT EXISTS projects (
	id INT AUTO_INCREMENT PRIMARY KEY,
	user INT,
	name VARCHAR(255) NOT NULL,
	description VARCHAR(255) NOT NULL,
	approved BOOLEAN DEFAULT false,
	FOREIGN KEY (user) REFERENCES users(id) ON DELETE CASCADE
);

-- schema rollback

DROP TABLE projects;
