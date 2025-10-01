-- Dummy Data for 'users' table

-- Instructors (account_type = 0)

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `bio`)
VALUES ('Dr. Evelyn Reed', 'i1@i.com', '1', 0, 0, 'Professor of Computer Science with a focus on AI and machine learning.');

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `bio`)
VALUES ('Dr. Samuel Chen', 'i2@i.com', '1', 0, 0, 'Specializing in database systems and web application architecture.');

-- Business Users (account_type = 1, role = 1)

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `bio`)
VALUES ('Innovate Corp', 'b1@b.com', '1', 1, 1, 'A leading tech company focused on developing cutting-edge business solutions.');

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `bio`)
VALUES ('DataDriven Inc.', 'b2@b.com', '1', 1, 1, 'We turn data into actionable insights for businesses of all sizes.');

-- Students (account_type = 3)

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `instructor_id`, `graduation`, `bio`)
VALUES ('Alice Johnson', 's1@s.com', '1', 3, 0, 1, 'Fall 2025', 'Senior student passionate about front-end development and UX design.');

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `instructor_id`, `graduation`, `bio`)
VALUES ('Bob Williams', 's2@s.com', '1', 3, 0, 1, 'Spring 2026', 'Junior student interested in cybersecurity and network protocols.');

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `instructor_id`, `graduation`, `bio`)
VALUES ('Charlie Brown', 's3@s.com', '1', 3, 0, 2, 'Fall 2025', 'Backend developer with experience in Python and Node.js.');

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `instructor_id`, `graduation`, `bio`)
VALUES ('Diana Miller', 's4@s.com', '1', 3, 0, 2, 'Spring 2027', 'Sophomore exploring data science and analytics.');

INSERT INTO `users` (`name`, `email`, `password`, `account_type`, `role`, `instructor_id`, `graduation`, `bio`)
VALUES ('Ethan Davis', 's5@s.com', '1', 3, 0, 1, 'Fall 2026', 'Aspiring mobile app developer for iOS and Android.');

-- Dummy Data for 'projects' table

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'E-commerce Recommendation Engine', 'A machine learning model that provides personalized product recommendations to online shoppers.', 1, 'https://example.com/project-ecom-rec', 'https://github.com/innovatecorp/ecom-rec');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Supply Chain Optimization Dashboard', 'A real-time analytics platform to monitor and optimize logistics,
from manufacturing to final delivery.', 2, 'https://example.com/project-supply-chain', 'https://github.com/datadriven/supply-chain');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Mobile Banking Application', 'A secure and user-friendly mobile app for personal banking, including transfers, payments, and account management.', 0, 'https://example.com/project-mobile-bank', 'https://github.com/innovatecorp/mobile-bank');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Customer Churn Prediction Model', 'Using historical data to predict which customers are at risk of leaving, allowing for proactive retention efforts.', 1, 'https://example.com/project-churn', 'https://github.com/datadriven/churn-model');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Virtual Reality Training Simulation', 'A VR application to train employees in complex or hazardous tasks in a safe, simulated environment.', 1, 'https://example.com/project-vr-training', 'https://github.com/innovatecorp/vr-training');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Social Media Sentiment Analysis', 'A tool that tracks brand mentions across social media and analyzes public sentiment in real-time.', 2, 'https://example.com/project-sentiment', 'https://github.com/datadriven/sentiment-analysis');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Smart Home IoT Hub', 'A central hub to connect and manage various smart home devices (lights, thermostats, security) through a single interface.', 1, 'https://example.com/project-smarthome', 'https://github.com/innovatecorp/smarthome');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Automated Financial Fraud Detection', 'An AI system that analyzes transactions to identify and flag suspicious activity, reducing financial losses.', 0, 'https://example.com/project-fraud-detect', 'https://github.com/datadriven/fraud-detection');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Telemedicine Video Conferencing Platform', 'A secure, HIPAA-compliant platform for doctors and patients to conduct virtual consultations.', 2, 'https://example.com/project-telemed', 'https://github.com/innovatecorp/telemedicine');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Dynamic Pricing Engine for Retail', 'An algorithm that adjusts product prices based on demand, competition, and inventory levels to maximize revenue.', 1, 'https://example.com/project-pricing', 'https://github.com/datadriven/pricing-engine');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Cloud-Based Project Management Tool', 'A collaborative tool similar to Trello or Asana for teams to manage tasks, deadlines, and project workflows.', 1, 'https://example.com/project-pm-tool', 'https://github.com/innovatecorp/pm-tool');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Website A/B Testing and Analytics', 'A platform to allow marketers to easily run A/B tests on landing pages and track user engagement metrics.', 0, 'https://example.com/project-ab-test', 'https://github.com/datadriven/ab-testing');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'AI-Powered Resume Screening Tool', 'An application to help HR departments automatically screen and rank job applicants based on resume content.', 2, 'https://example.com/project-resume-ai', 'https://github.com/innovatecorp/resume-ai');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Agricultural Crop Yield Prediction', 'Using satellite imagery and weather data to predict crop yields for farmers and commodities traders.', 1, 'https://example.com/project-crop-yield', 'https://github.com/datadriven/crop-yield');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Language Learning Mobile App', 'An interactive app for learning new languages featuring gamification, speech recognition, and spaced repetition.', 1, 'https://example.com/project-lang-app', 'https://github.com/innovatecorp/lang-app');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Market Basket Analysis for Grocers', 'Analyzing transaction data to discover which products are frequently bought together, in order to optimize store layout and promotions.', 0, 'https://example.com/project-market-basket', 'https://github.com/datadriven/market-basket');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Event Ticketing and Management System', 'A web platform for creating, promoting, and selling tickets for events of all sizes.', 2, 'https://example.com/project-ticketing', 'https://github.com/innovatecorp/ticketing');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Personalized News Aggregator', 'A content platform that learns user preferences and delivers a customized feed of news articles and blog posts.', 1, 'https://example.com/project-news-agg', 'https://github.com/datadriven/news-aggregator');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Restaurant Reservation and Table Management', 'A system for restaurants to manage online reservations, table assignments, and waitlists.', 1, 'https://example.com/project-restaurant', 'https://github.com/innovatecorp/restaurant-booking');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'HR Employee Performance Analytics', 'A dashboard for managers to track employee performance metrics,
set goals, and identify trends over time.', 0, 'https://example.com/project-hr-analytics', 'https://github.com/datadriven/hr-analytics');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Subscription Box Service Platform', 'A turnkey solution for businesses to launch and manage their own subscription box service.', 2, 'https://example.com/project-sub-box', 'https://github.com/innovatecorp/sub-box');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Ad Campaign ROI Calculator', 'A tool that integrates with ad platforms to automatically calculate and visualize the return on investment for marketing campaigns.', 1, 'https://example.com/project-ad-roi', 'https://github.com/datadriven/ad-roi');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Fitness and Workout Tracking App', 'A mobile app that allows users to log workouts, track progress, and follow personalized fitness plans.', 1, 'https://example.com/project-fitness-app', 'https://github.com/innovatecorp/fitness-app');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (4, 'Real Estate Price Prediction Model', 'An algorithm that predicts housing prices based on location, features, and historical market data.', 0, 'https://example.com/project-real-estate', 'https://github.com/datadriven/real-estate-model');

INSERT INTO `projects` (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
VALUES (3, 'Online Code Editor and Collaboration Tool', 'A browser-based IDE that allows multiple developers to code together in real-time, similar to VS Code Live Share.', 2, 'https://example.com/project-live-editor', 'https://github.com/innovatecorp/live-editor');
