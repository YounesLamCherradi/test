from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import os
from bson.objectid import ObjectId
from datetime import datetime
from werkzeug.utils import secure_filename
import oauth
from authlib.integrations.flask_client import OAuth
import secrets  # Add this import at the top of your file
import joblib
import pandas as pd
import re
import os
import fitz 
import openai



app = Flask(__name__)
app.secret_key = os.urandom(24)  
app.config['UPLOAD_FOLDER'] = 'uploads'

# MongoDB connection
client = MongoClient('mongodb+srv://younes:CGBmJoqjiL3aEJ5U@recruitpro.dsmqp.mongodb.net/RecruitPro?retryWrites=true&w=majority&appName=RecruitPro')
db = client['RecruitPro']
collection = db['users']
posts_collection = db['posts']
applications_collection = db['applications']  
notifications_collection = db['notifications']  



# Function to preprocess the text
def preprocess_text(resumeText):
    resumeText = re.sub(r'\d+', '', resumeText)  
    resumeText = re.sub(r'[^\w\s]', ' ', resumeText) 
    resumeText = resumeText.lower()  
    return resumeText


@app.route('/welcome')
def welcome():
    return render_template('home.html')



# Set your OpenAI API key
openai.api_key= "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"



def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text





# SIGNUP ROUTE
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        alumni = 'alumni' in request.form  

       
        user_exists = collection.find_one({'email': email})
        if user_exists:
            flash('Email already exists.', 'danger')
            return render_template('signup.html')

        
        new_user = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,  
            'alumni': alumni,
            'role': 'user'  
        }
        
        
        result = collection.insert_one(new_user)
        
        session['user_id'] = str(result.inserted_id)  
        session['email'] = email
        session['role'] = 'user'  
        session['logged_in'] = True  

        flash('Signup successful! You are now logged in.', 'success')
       
        return redirect(url_for('user_dashboard'))
    
    return render_template('signup.html')




# LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        
        user = collection.find_one({'email': email, 'password': password})

        if user:
            
            session['user_id'] = str(user['_id'])  # User ID
            session['email'] = user['email']  # User email
            session['first_name'] = user.get('first_name') 
            session['role'] = user.get('role', 'user')  # User role; default to 'user'
            session['logged_in'] = True  # Set logged-in status

            flash('Logged in successfully!', 'success')

            # Redirect based on user role
            if session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))  # For regular users
        else:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

    return render_template('login.html')


# HOME ROUTE (Regular User Dashboard)
@app.route('/home')
def home():
    if 'user_id' in session and session.get('role') == 'user':
        return render_template('home.html', email=session['email'])
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

# ADMIN DASHBOARD ROUTE
@app.route('/admin-dashboard')
def admin_dashboard():
    if 'user_id' in session and session.get('role') == 'admin':
        print("First name from session:", session.get('first_name'))  # Debugging line

        return render_template('admin_dashboard.html', first_name=session.get('first_name'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

# USER DASHBOARD ROUTE
@app.route('/user-dashboard') 
def user_dashboard():
    if 'logged_in' in session and session['logged_in']:
        return render_template('applicant_dashboard.html', username=session['email'], first_name=session.get('first_name'))  # Correctly pass email as username
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))



@app.route('/track-applications')
def track_applications():
    if 'user_id' in session and session.get('role') == 'user':
        # Fetch applications for the logged-in user
        user_email = session['email']
        applications = list(applications_collection.find({'applicant_email': user_email}))
        return render_template('applicant_tracking.html', applications=applications, first_name=session.get('first_name'))
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))



@app.route('/update-stage/<application_id>', methods=['POST'])
def update_stage(application_id):
    if 'user_id' in session and session.get('role') == 'admin':
        new_stage = request.json.get('stage')
        
        if new_stage:
            # Find the application by ID
            application = applications_collection.find_one({'_id': ObjectId(application_id)})
            if not application:
                return jsonify({"success": False, "message": "Application not found"}), 404
            
            # Update the application's status
            applications_collection.update_one(
                {'_id': ObjectId(application_id)},
                {'$set': {'status': new_stage}}
            )
            
            # Add a notification for the applicant
            notification = {
                'applicant_email': application['applicant_email'],  # Link to the applicant's email
                'message': f"Your application for '{application.get('position_title', 'Unknown Position')}' is now {new_stage}.",  # Clear, readable message
                'timestamp': datetime.utcnow(),  # Store timestamp for notification
                'read': False  # Mark notification as unread initially
            }
            # Insert the notification into the notifications collection
            notifications_collection.insert_one(notification)
            
            return jsonify({"success": True, "message": "Stage updated and notification sent"}), 200
        else:
            return jsonify({"success": False, "message": "Invalid stage"}), 400
    else:
        return jsonify({"success": False, "message": "Unauthorized access"}), 403



@app.route('/get-notifications')
def get_notifications():
    if 'user_id' in session and session.get('role') == 'user':
        user_email = session['email']
        # Fetch only unread notifications
        unread_notifications = list(notifications_collection.find(
            {'applicant_email': user_email, 'read': False},  # Filter unread notifications
            {'message': 1, '_id': 0}
        ))
        return jsonify(unread_notifications)
    else:
        return jsonify({"error": "Unauthorized access"}), 403





@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    if 'user_id' in session and session.get('role') == 'user':
        user_email = session['email']
        # Mark all unread notifications as read for the user
        notifications_collection.update_many(
            {'applicant_email': user_email, 'read': False}, 
            {'$set': {'read': True}}
        )
        return jsonify({"message": "Notifications marked as read"}), 200
    else:
        return jsonify({"error": "Unauthorized access"}), 403






# VIEW REPORTS ROUTE
@app.route('/view-reports')
def view_reports():
    # Ensure only admins can access this route
    if 'user_id' in session and session.get('role') == 'admin':
        # Placeholder logic for viewing reports; fetch or generate data as needed
        reports_data = []  # Replace with actual data fetching logic
        return render_template('view_reports.html', reports=reports_data)
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

# USER MANAGEMENT ROUTE
@app.route('/user-management')
def user_management():
    # Ensure only admins can access this route
    if 'user_id' in session and session.get('role') == 'admin':
        users = list(collection.find())
        return render_template('admin_user_management.html', users=users, first_name=session.get('first_name'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


@app.route('/manage-vacancies')
def manage_vacancies():
    if 'user_id' in session and session.get('role') == 'admin':
        vacancies = list(posts_collection.find())  # Change variable name to 'vacancies' for consistency
        return render_template('admin_manage_vacancies.html', vacancies=vacancies, first_name=session.get('first_name'))  # Pass 'vacancies' to match the HTML
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


# USER MANAGEMENT ROUTE
@app.route('/user-management')
def manage_users():  # Renamed to avoid conflict
    if 'user_id' in session and session.get('role') == 'admin':
        # Retrieve all users from the collection
        users = list(collection.find())
        return render_template('admin_user_management.html', users=users)
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


# ADD USER ROUTE
@app.route('/add-user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' in session and session.get('role') == 'admin':
        if request.method == 'POST':
            # Collect user details from the form
            username = request.form.get('username')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')  # Role can be 'user' or 'admin'

            # Check if the email is already registered
            user_exists = collection.find_one({'email': email})
            if user_exists:
                flash('Email already exists.', 'danger')
                return redirect(url_for('add_user'))

            # Insert new user into the database
            new_user = {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'password': password,  # Hash password in production
                'role': role
            }
            collection.insert_one(new_user)
            flash('User added successfully!', 'success')
            return redirect(url_for('user_management'))

        return render_template('admin_add_user.html', first_name=session.get('first_name'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

from datetime import datetime

# Define keywords for scoring
KEYWORDS = ['French', 'Arabic', 'English', 'Python', 'CCNA', 'Project Management']

# Function to score resumes based on keyword presence
def score_resume(resumeText):
    score = 0
    for keyword in KEYWORDS:
        if keyword.lower() in resumeText.lower():
            score += 1  # Increment score for each keyword found
    # Normalize the score to a scale of 10
    return (score / len(KEYWORDS)) * 10

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

@app.route('/submit-application/<position_id>', methods=['POST'])
def submit_application(position_id):
    if 'user_id' in session and session.get('role') == 'user':
        applicant_name = request.form.get('applicant_name')
        applicant_email = session['email']
        cover_letter = request.form.get('cover_letter')

        # Handle file upload
        resume_file = request.files.get('resume')
        if resume_file and resume_file.filename:
            filename = secure_filename(resume_file.filename)
            resume_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(resume_file_path)
        else:
            flash("No resume file uploaded.", 'danger')
            return redirect(url_for('user_dashboard'))

        # Extract text from the uploaded CV (PDF)
        cv_text = extract_text_from_pdf(resume_file_path)

        # Send CV text to ChatGPT for evaluation
        prompt = f"""
        Evaluate the following CV based on the provided algorithm:
        1. Length: Deduct points if the CV exceeds 2000 words.
        2. Errors: Deduct points for spelling/grammar issues.
        3. Formality: Deduct points for informal or unprofessional tone.
        4. Keywords: Score based on job-relevant keywords.
        5. Experience: Assign points based on work history relevance.
        6. Education: Score based on qualifications and institution ranking.
        7. Languages: Full points for English and French fluency; bonuses for others.

        Respond strictly with:
        - "yes" if the CV meets the criteria, followed by up to 5 relevant job position keywords separated by commas.
        - "no" if the CV does not meet the criteria, with no additional information.

        CV Text:
        {cv_text}
        """
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert resume evaluator."},
                {"role": "user", "content": prompt}
            ]
        )

        # Parse ChatGPT response
        result = response['choices'][0]['message']['content'].strip().lower()

        # Initialize default values
        status = "no"
        tags = []

        # Parse response for "yes" or "no" and extract tags if applicable
        if result.startswith("yes"):
            status = "yes"
            parts = result.split("yes", 1)  # Split after "yes"
            if len(parts) > 1:
                tags = [tag.strip() for tag in parts[1].split(",") if tag.strip()]  # Extract tags
        elif result.startswith("no"):
            status = "no"
            tags = []  # No tags for unacceptable CVs
        else:
            flash("Unexpected response from ChatGPT. Please try again.", "danger")
            return redirect(url_for('user_dashboard'))

        # Fetch the position title based on position_id
        position = posts_collection.find_one({'_id': ObjectId(position_id)})
        position_title = position['title'] if position else 'Unknown Position'

        # Insert the application data into the database
        applications_collection.insert_one({
            'position_title': position_title,
            'applicant_name': applicant_name,
            'applicant_email': applicant_email,
            'resume_filename': filename,
            'cover_letter': cover_letter,
            'status': "In progres",
            'Ai_score': status,
            'tags': tags,
            'application_date': datetime.now().strftime('%Y-%m-%d')
        })

        flash(f'Application submitted successfully! Status: {status.upper()}', 'success')
        return redirect(url_for('user_dashboard'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


#@app.route('/search_candidates', methods=['GET', 'POST'])
#def search_candidates():
 #   return render_template("jonas.html")




# DELETE USER ROUTE
@app.route('/delete-user/<user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' in session and session.get('role') == 'admin':
        collection.delete_one({'_id': ObjectId(user_id)})
        flash('User deleted successfully!', 'success')
        return redirect(url_for('user_management'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


@app.route('/search_candidates', methods=['GET', 'POST'])
def search_candidates():
    # Check if the admin is logged in
    if 'user_id' in session and session.get('role') == 'admin':
        admin_name = session.get('first_name')  # Retrieve admin name from session

        if request.method == 'POST':
            # Get the position description and keywords from the form
            description = request.form.get('description', '').strip()
            keywords = request.form.get('keywords', '').strip().split(',')

            # Ensure keywords are processed correctly (remove whitespace and convert to lowercase)
            keywords = [keyword.strip().lower() for keyword in keywords if keyword.strip()]

            # Query the database: Fetch CVs where at least one keyword matches
            matching_cvs = list(applications_collection.find({'tags': {'$in': keywords}}))

            # Render the search results
            return render_template(
                'admin_search_cv.html', 
                results=matching_cvs, 
                description=description, 
                keywords=keywords, 
                admin_name=admin_name
            )

        # Render the search form if GET request
        return render_template('admin_search_cv.html', admin_name=admin_name)

    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


@app.route('/create-position', methods=['POST'])
def create_position():
    if 'user_id' in session and session.get('role') == 'admin':
        title = request.form.get('title')
        location = request.form.get('location')
        description = request.form.get('description')

        new_post = {
            'title': title,
            'location': location,
            'description': description
        }
        posts_collection.insert_one(new_post)
        flash('Position created successfully!', 'success')
        return redirect(url_for('manage_vacancies'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

# EDIT POSITION ROUTE
@app.route('/edit-position/<post_id>', methods=['GET', 'POST'])
def edit_position(post_id):
    if 'user_id' in session and session.get('role') == 'admin':
        post = posts_collection.find_one({'_id': ObjectId(post_id)})
        if request.method == 'POST':
            updated_title = request.form.get('title')
            updated_location = request.form.get('location')
            updated_description = request.form.get('description')

            posts_collection.update_one(
                {'_id': ObjectId(post_id)},
                {'$set': {
                    'title': updated_title,
                    'location': updated_location,
                    'description': updated_description
                }}
            )
            flash('Position updated successfully!', 'success')
            return redirect(url_for('manage_vacancies'))
        
        return render_template('admin_edit_position.html', post=post)  # Ensure 'post' is passed here
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

# DELETE POSITION ROUTE
@app.route('/delete-position/<post_id>', methods=['POST'])
def delete_position(post_id):
    if 'user_id' in session and session.get('role') == 'admin':
        posts_collection.delete_one({'_id': ObjectId(post_id)})
        flash('Position deleted successfully!', 'success')
        return redirect(url_for('manage_vacancies'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))


# Route to display all applications
@app.route('/check-applications')
def check_applications():
    if 'user_id' in session and session.get('role') == 'admin':
        # Retrieve applications from the database
        applications = list(applications_collection.find())
        return render_template('check_application.html', applications=applications, admin_name=session.get('first_name'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

@app.route('/available-vacancies')
def available_positions():
    if 'user_id' in session and session.get('role') == 'user':
        # Fetch available positions from the database
        positions = list(posts_collection.find())  # Adjust this query as needed
        return render_template('available_position.html', first_name=session.get('first_name'), positions=positions)
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

@app.route('/apply/<position_id>', methods=['GET', 'POST'])
def apply(position_id):
    if 'user_id' in session and session.get('role') == 'user':
        position = posts_collection.find_one({'_id': ObjectId(position_id)})
        
        if request.method == 'POST':
            # Redirect to submit_application to handle the form submission
            return redirect(url_for('submit_application', position_id=position_id))

        # Render the application form for GET requests
        return render_template('applicant_submit_application.html', position=position, first_name=session.get('first_name'))  # Pass the position variable
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

# Renaming the route function to avoid conflict
@app.route('/submit-application/<position_id>', methods=['POST'])
def submit_application_form(position_id):
    if 'user_id' in session and session.get('role') == 'user':
        applicant_name = request.form.get('applicant_name')
        applicant_email = request.form.get('applicant_email')
        cover_letter = request.form.get('cover_letter')
        resume_filename = request.form.get('resume')

        applications_collection.insert_one({
            'position_id': position_id,
            'applicant_name': applicant_name,
            'applicant_email': applicant_email,
            'resume_filename': resume_filename,
            'cover_letter': cover_letter,
            'status': 'Submitted'
        })

        flash('Application submitted successfully!', 'success')
        return redirect(url_for('user_dashboard'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))



# Route to view application details
@app.route('/application-details/<application_id>')
def application_details(application_id):
    if 'user_id' in session and session.get('role') == 'admin':
        # Fetch specific application from the database
        application = applications_collection.find_one({'_id': ObjectId(application_id)})
        if not application:
            flash("Application not found.", "danger")
            return redirect(url_for('check_applications'))

        # Optionally fetch related position data if needed
        position = posts_collection.find_one({'_id': ObjectId(application['position_id'])}) if 'position_id' in application else None
        return render_template('application_details.html', application=application, position=position)
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))




# LOGOUT ROUTE
@app.route('/logout')
def logout():
    session.clear()  # Clears session data to log out the usercls

    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

##################################################################



# Run the application
if __name__ == '__main__':
    app.run(debug=True)
