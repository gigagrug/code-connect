import bcrypt
from sqlalchemy import text

def seed_data(engine):
    print("--- Seeding data from dummydata.py ---")
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                # 1. SEED USERS (with Bcrypt Hashing)
                print("Seeding users...")
                users_data = [
                    {'name': 'Dr. Evelyn Reed', 'email': 'i1@i.com', 'password': '1', 'role': 0, 'permission': 0, 'bio': None, 'instructor_id': None, 'graduation': None},
                    {'name': 'Dr. Samuel Chen', 'email': 'i2@i.com', 'password': '1', 'role': 0, 'permission': 0, 'bio': None, 'instructor_id': None, 'graduation': None},
                    {'name': 'Innovate Corp', 'email': 'b1@b.com', 'password': '1', 'role': 1, 'permission': 1, 'bio': 'A leading tech company focused on developing cutting-edge business solutions.', 'instructor_id': None, 'graduation': None},
                    {'name': 'DataDriven Inc.', 'email': 'b2@b.com', 'password': '1', 'role': 1, 'permission': 1, 'bio': 'We turn data into actionable insights for businesses of all sizes.', 'instructor_id': None, 'graduation': None},
                    {'name': 'Alice Johnson', 'email': 's1@s.com', 'password': '1', 'role': 3, 'permission': 0, 'bio': None, 'instructor_id': 1, 'graduation': 'Fall 2025'},
                    {'name': 'Bob Williams', 'email': 's2@s.com', 'password': '1', 'role': 3, 'permission': 0, 'bio': None, 'instructor_id': 1, 'graduation': 'Spring 2026'},
                    {'name': 'Charlie Brown', 'email': 's3@s.com', 'password': '1', 'role': 3, 'permission': 0, 'bio': None, 'instructor_id': 2, 'graduation': 'Fall 2025'},
                    {'name': 'Diana Miller', 'email': 's4@s.com', 'password': '1', 'role': 3, 'permission': 0, 'bio': None, 'instructor_id': 2, 'graduation': 'Spring 2027'},
                    {'name': 'Ethan Davis', 'email': 's5@s.com', 'password': '1', 'role': 3, 'permission': 0, 'bio': None, 'instructor_id': 1, 'graduation': 'Fall 2026'},
                ]

                user_insert_query = text("""
                    INSERT INTO users (name, email, password, role, permission, bio, instructor_id, graduation)
                    VALUES (:name, :email, :password, :role, :permission, :bio, :instructor_id, :graduation)
                """)

                for user in users_data:
                    hashed_pw = bcrypt.hashpw(user['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    user['password'] = hashed_pw
                    connection.execute(user_insert_query, user)
                
                print(f"✅ Inserted {len(users_data)} users.")

                # 2. SEED PROJECTS
                print("Seeding projects...")
                insert_projects_sql = text("""
                    INSERT INTO `projects`
                        (`user_id`, `name`, `description`, `status`, `project_link`, `github_link`)
                    VALUES
                        (3, 'E-commerce Recommendation Engine', 'A machine learning model that provides personalized product recommendations to online shoppers.', 0, 'https://example.com/project-ecom-rec', 'https://github.com/innovatecorp/ecom-rec'),
                        (4, 'Supply Chain Optimization Dashboard', 'A real-time analytics platform to monitor and optimize logistics, from manufacturing to final delivery.', 0, 'https://example.com/project-supply-chain', 'https://github.com/datadriven/supply-chain'),
                        (3, 'Mobile Banking Application', 'A secure and user-friendly mobile app for personal banking, including transfers, payments, and account management.', 0, 'https://example.com/project-mobile-bank', 'https://github.com/innovatecorp/mobile-bank'),
                        (4, 'Customer Churn Prediction Model', 'Using historical data to predict which customers are at risk of leaving, allowing for proactive retention efforts.', 0, 'https://example.com/project-churn', 'https://github.com/datadriven/churn-model'),
                        (3, 'Virtual Reality Training Simulation', 'A VR application to train employees in complex or hazardous tasks in a safe, simulated environment.', 0, 'https://example.com/project-vr-training', 'https://github.com/innovatecorp/vr-training'),
                        (4, 'Social Media Sentiment Analysis', 'A tool that tracks brand mentions across social media and analyzes public sentiment in real-time.', 0, 'https://example.com/project-sentiment', 'https://github.com/datadriven/sentiment-analysis'),
                        (3, 'Smart Home IoT Hub', 'A central hub to connect and manage various smart home devices (lights, thermostats, security) through a single interface.', 0, 'https://example.com/project-smarthome', 'https://github.com/innovatecorp/smarthome'),
                        (4, 'Automated Financial Fraud Detection', 'An AI system that analyzes transactions to identify and flag suspicious activity, reducing financial losses.', 0, 'https://example.com/project-fraud-detect', 'https://github.com/datadriven/fraud-detection'),
                        (3, 'Telemedicine Video Conferencing Platform', 'A secure, HIPAA-compliant platform for doctors and patients to conduct virtual consultations.', 0, 'https://example.com/project-telemed', 'https://github.com/innovatecorp/telemedicine'),
                        (4, 'Dynamic Pricing Engine for Retail', 'An algorithm that adjusts product prices based on demand, competition, and inventory levels to maximize revenue.', 0, 'https://example.com/project-pricing', 'https://github.com/datadriven/pricing-engine'),
                        (3, 'Cloud-Based Project Management Tool', 'A collaborative tool similar to Trello or Asana for teams to manage tasks, deadlines, and project workflows.', 0, 'https://example.com/project-pm-tool', 'https://github.com/innovatecorp/pm-tool'),
                        (4, 'Website A/B Testing and Analytics', 'A platform to allow marketers to easily run A/B tests on landing pages and track user engagement metrics.', 0, 'https://example.com/project-ab-test', 'https://github.com/datadriven/ab-testing'),
                        (3, 'AI-Powered Resume Screening Tool', 'An application to help HR departments automatically screen and rank job applicants based on resume content.', 0, 'https://example.com/project-resume-ai', 'https://github.com/innovatecorp/resume-ai'),
                        (4, 'Agricultural Crop Yield Prediction', 'Using satellite imagery and weather data to predict crop yields for farmers and commodities traders.', 0, 'https://example.com/project-crop-yield', 'https://github.com/datadriven/crop-yield'),
                        (3, 'Language Learning Mobile App', 'An interactive app for learning new languages featuring gamification, speech recognition, and spaced repetition.', 0, 'https://example.com/project-lang-app', 'https://github.com/innovatecorp/lang-app'),
                        (4, 'Market Basket Analysis for Grocers', 'Analyzing transaction data to discover which products are frequently bought together, in order to optimize store layout and promotions.', 0, 'https://example.com/project-market-basket', 'https://github.com/datadriven/market-basket'),
                        (3, 'Event Ticketing and Management System', 'A web platform for creating, promoting, and selling tickets for events of all sizes.', 0, 'https://example.com/project-ticketing', 'https://github.com/innovatecorp/ticketing'),
                        (4, 'Personalized News Aggregator', 'A content platform that learns user preferences and delivers a customized feed of news articles and blog posts.', 0, 'https://example.com/project-news-agg', 'https://github.com/datadriven/news-aggregator'),
                        (3, 'Restaurant Reservation and Table Management', 'A system for restaurants to manage online reservations, table assignments, and waitlists.', 0, 'https://example.com/project-restaurant', 'https://github.com/innovatecorp/restaurant-booking'),
                        (4, 'HR Employee Performance Analytics', 'A dashboard for managers to track employee performance metrics, set goals, and identify trends over time.', 0, 'https://example.com/project-hr-analytics', 'https://github.com/datadriven/hr-analytics'),
                        (3, 'Subscription Box Service Platform', 'A turnkey solution for businesses to launch and manage their own subscription box service.', 0, 'https://example.com/project-sub-box', 'https://github.com/innovatecorp/sub-box'),
                        (4, 'Ad Campaign ROI Calculator', 'A tool that integrates with ad platforms to automatically calculate and visualize the return on investment for marketing campaigns.', 0, 'https://example.com/project-ad-roi', 'https://github.com/datadriven/ad-roi'),
                        (3, 'Fitness and Workout Tracking App', 'A mobile app that allows users to log workouts, track progress, and follow personalized fitness plans.', 0, 'https://example.com/project-fitness-app', 'https://github.com/innovatecorp/fitness-app'),
                        (4, 'Real Estate Price Prediction Model', 'An algorithm that predicts housing prices based on location, features, and historical market data.', 0, 'https://example.com/project-real-estate', 'https://github.com/datadriven/real-estate-model'),
                        (3, 'Online Code Editor and Collaboration Tool', 'A browser-based IDE that allows multiple developers to code together in real-time, similar to VS Code Live Share.', 0, 'https://example.com/project-live-editor', 'https://github.com/innovatecorp/live-editor');
                """)
                result = connection.execute(insert_projects_sql)
                print(f"✅ Inserted {result.rowcount} projects.")


                # 3. SEED JOBS
                print("Seeding jobs...")
                insert_jobs_sql = text("""
                    INSERT INTO `jobs`
                        (`user_id`, `title`, `description`, `link`, `status`)
                    VALUES
                        (3, 'Senior Frontend Developer (React)', 'Innovate Corp is seeking an experienced React developer to lead the development of our new project management platform. You will be responsible for building a high-performance, responsive UI and mentoring junior developers.', 'https://www.example.com', 1),
                        (4, 'Data Scientist - Machine Learning', 'DataDriven Inc. is looking for a Data Scientist with expertise in machine learning and Python. You will work on our predictive analytics models, including customer churn and fraud detection systems.', 'https://www.example.com', 1),
                        (3, 'Mobile Developer (iOS/Swift)', 'Join our mobile team at Innovate Corp to build our next-generation mobile banking and telemedicine applications. Strong experience with Swift and building secure, scalable apps is required.', '', 1),
                        (4, 'Business Intelligence Analyst', 'We need a BI Analyst to join our team at DataDriven Inc. You will be responsible for creating dashboards (Tableau/Power BI), analyzing supply chain data, and providing actionable insights to our clients.', '', 1),
                        (3, 'Cloud Infrastructure Engineer (AWS)', 'Innovate Corp is hiring a Cloud Engineer to manage our growing AWS infrastructure. You will be responsible for CI/CD pipelines, container orchestration (Kubernetes), and ensuring high availability for all our platforms.', 'https://www.example.com', 1),
                        (4, 'Junior Data Analyst', 'This is an-level position at DataDriven Inc. for a recent graduate. You will assist our senior analysts with data cleaning, report generation, and market basket analysis. (This is a draft and not yet open).', 'https://www.example.com', 0);
                """)
                result = connection.execute(insert_jobs_sql)
                print(f"✅ Inserted {result.rowcount} jobs.")
                
            # Transaction is committed here
        print("✅ Dummy data seeding complete.")

    except Exception as e:
        # Transaction is rolled back automatically on exception
        print(f"❌ Error seeding data: {e}")
        raise # Re-raise exception to stop the startup process if seeding fails
