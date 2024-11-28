# Necessary Imports
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
import os
from bson.objectid import ObjectId
from datetime import datetime
from werkzeug.utils import secure_filename
import oauth
from authlib.integrations.flask_client import OAuth
import secrets  # For generating secure tokens
import joblib
import pandas as pd
import re
import os
import fitz  # For PDF text extraction
import openai  # For ChatGPT integration

# Flask App Configuration
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session handling
app.config['UPLOAD_FOLDER'] = 'uploads'  # Folder for storing uploaded files

# MongoDB Connection
client = MongoClient('your_connection_string')  # Replace with your MongoDB connection string
db = client['RecruitPro']  # Database name
collection = db['users']  # Users collection
posts_collection = db['posts']  # Job postings collection
applications_collection = db['applications']  # Job applications collection
notifications_collection = db['notifications']  # Notifications collection

# Set your OpenAI API key (ChatGPT)
openai.api_key= "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"
# Replace with your actual OpenAI API key

# Utility Function: Preprocess Text
def preprocess_text(resumeText):
    """
    Prepares resume text by removing numbers, punctuation, and converting to lowercase.
    """
    resumeText = re.sub(r'\d+', '', resumeText)  # Remove numbers
    resumeText = re.sub(r'[^\w\s]', ' ', resumeText)  # Remove special characters
    resumeText = resumeText.lower()  # Convert to lowercase
    return resumeText

# Utility Function: Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    """
    Extracts all text from a PDF file.
    """
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

# Welcome Route
@app.route('/welcome')
def welcome():
    """
    Displays the welcome page.
    """
    return render_template('home.html')

# Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Handles user signup:
    - Displays signup form (GET).
    - Registers new user in the database and initiates a session (POST).
    """
    if request.method == 'POST':
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        alumni = 'alumni' in request.form  # Alumni checkbox

        # Check if email is already registered
        user_exists = collection.find_one({'email': email})
        if user_exists:
            flash('Email already exists.', 'danger')
            return render_template('signup.html')

        # Register new user
        new_user = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,
            'alumni': alumni,
            'role': 'user'  # Default role is 'user'
        }
        result = collection.insert_one(new_user)

        # Start session
        session['user_id'] = str(result.inserted_id)
        session['email'] = email
        session['role'] = 'user'
        session['logged_in'] = True

        flash('Signup successful! You are now logged in.', 'success')
        return redirect(url_for('user_dashboard'))

    return render_template('signup.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login:
    - Displays login form (GET).
    - Verifies user credentials and starts a session (POST).
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Verify credentials
        user = collection.find_one({'email': email, 'password': password})
        if user:
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['first_name'] = user.get('first_name')
            session['role'] = user.get('role', 'user')
            session['logged_in'] = True

            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard' if session['role'] == 'admin' else 'user_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')

# User Dashboard
@app.route('/user-dashboard')
def user_dashboard():
    """
    Displays the user dashboard for logged-in users.
    """
    if 'logged_in' in session and session['logged_in']:
        return render_template('applicant_dashboard.html', username=session['email'], first_name=session.get('first_name'))
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

# Admin Dashboard
@app.route('/admin-dashboard')
def admin_dashboard():
    """
    Displays the admin dashboard for logged-in admins.
    """
    if 'user_id' in session and session.get('role') == 'admin':
        return render_template('admin_dashboard.html', first_name=session.get('first_name'))
    else:
        flash("You do not have access to this page.", "warning")
        return redirect(url_for('login'))

# Logout Route
@app.route('/logout')
def logout():
    """
    Logs out the user by clearing session data.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Main Runner
if __name__ == '__main__':
    app.run(debug=True)
