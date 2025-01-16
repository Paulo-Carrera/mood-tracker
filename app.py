from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta
import os

# Load environment variables
load_dotenv()

# Flask setup
app = Flask(__name__)
CORS(app, origins=["*"])  # Allow all domains for debugging purposes
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")  # Replace with a strong secret key

# Flask extensions
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Supabase setup
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, email, username=None):
        self.id = id
        self.email = email
        self.username = username

# Load user callback
@login_manager.user_loader
def load_user(user_id):
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not response.data:
        print(f"Error loading user: {response}")
        return None
    user = response.data[0]
    return User(id=user["id"], email=user["email"], username=user.get("username"))

# Routes
@app.route("/")
@login_required
def home():
    return render_template("index.html", username=current_user.username)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")
        if not email or not password or not username:
            flash("Email, password, and username are required", "error")
            return redirect(url_for('register'))
        try:
            existing_user = supabase.table("users").select("*").eq("username", username).execute()
            existing_email = supabase.table("users").select("*").eq("email", email).execute()
            if existing_user.data:
                flash("Username already taken", "error")
                return redirect(url_for('register'))
            if existing_email.data:
                flash("Email already registered", "error")
                return redirect(url_for('register'))
            hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
            response = supabase.table("users").insert({
                "email": email,
                "password": hashed_password,
                "username": username
            }).execute()
            if response.error:
                flash(f"Error inserting user: {response.error.message}", "error")
                return redirect(url_for('register'))
            flash("User registered successfully!", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error inserting user: {str(e)}", "error")
            return redirect(url_for('register'))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == "POST":
        identifier = request.form.get("email") or request.form.get("username")
        password = request.form.get("password")
        if not identifier or not password:
            flash("Email/Username and password are required", "error")
            return redirect(url_for('login'))
        response = supabase.table("users").select("*").eq("email", identifier).execute()
        if not response.data:
            response = supabase.table("users").select("*").eq("username", identifier).execute()
        user = response.data
        if not user or not bcrypt.check_password_hash(user[0]["password"], password):
            flash("Invalid email/username or password", "error")
            return redirect(url_for('login'))
        user_obj = User(id=user[0]["id"], email=user[0]["email"], username=user[0]["username"])
        login_user(user_obj)
        flash("Login successful!", "success")
        return redirect(url_for('home'))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully!", "success")
    return redirect(url_for('login'))

@app.route("/track_mood", methods=["GET", "POST"])
@login_required
def track_mood():
    predefined_moods = ["Happy", "Sad", "Anxious", "Tense", "Excited", "Angry", "Stressed", "Relaxed"]
    
    if request.method == "GET":
        return render_template("track_mood.html", moods=predefined_moods)
    
    if request.method == "POST":
        mood = request.form.get("mood")
        note = request.form.get("note", "")
        
        if not mood:
            flash("Please select a mood", "error")
            return redirect(url_for("track_mood"))
        
        try:
            response = supabase.table("moods").insert({
                "user_id": current_user.id,
                "mood": mood,
                "note": note
            }).execute()
            
            if response.error:
                flash(f"Error tracking mood: {response.error.message}", "error")
                return redirect(url_for("track_mood"))
            
            flash("Mood tracked successfully!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            flash(f"Error tracking mood: {str(e)}", "error")
            return redirect(url_for("track_mood"))

def fetch_all_moods_from_supabase():
    # Replace this with your actual Supabase fetching logic
    return supabase.table('moods').select('*').execute().data

@app.route('/get_moods', methods=["GET"])
@login_required
def get_moods():
    try:
        # Fetch all moods for the logged-in user
        response = supabase.table("moods").select("*").eq("user_id", current_user.id).execute()
        all_moods = response.data if response.data else []
    except Exception as e:
        flash(f"Error fetching moods: {str(e)}", "error")
        all_moods = []

    # Render the get_moods.html template with the moods data
    return render_template("get_moods.html", all_moods=all_moods)

def fetch_all_moods_from_supabase():
    # Replace this with your actual Supabase fetching logic
    return supabase.table('moods').select('*').execute().data



if __name__ == "__main__":
    app.run(debug=True)
