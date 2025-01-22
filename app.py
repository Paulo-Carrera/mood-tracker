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
    categorized_moods = {
    "positive": ["Happy", "Joyful", "Grateful", "Excited", "Peaceful", "Relaxed", "Optimistic", "Satisfied", "Loving"],
    "negative": ["Sad", "Angry", "Anxious", "Frustrated", "Overwhelmed", "Hopeless", "Tense", "Jealous", "Ashamed"],
    "neutral": ["Calm", "Content", "Indifferent", "Tired", "Uninterested", "Neutral", "Curious", "Mellow", "Accepting"],
    "high-energy": ["Energetic", "Productive", "Motivated", "Inspired", "Focused", "Determined", "Adventurous", "Cheerful", "Playful"],
    "low-energy": ["Drained", "Defeated", "Exhausted", "Lonely", "Melancholic", "Isolated", "Sleepy", "Burned Out", "Withdrawn"],
}
    
    if request.method == "GET":
        return render_template("track_mood.html", categorized_moods=categorized_moods)
    
    if request.method == "POST":
        moods = request.form.getlist("mood")  # Get multiple moods
        note = request.form.get("note", "")
        
        if not moods:
            flash("Please select at least one mood", "error")
            return redirect(url_for("track_mood"))
        
        try:
            # Insert each selected mood into the database
            for mood in moods:
                response = supabase.table("moods").insert({
                    "user_id": current_user.id,
                    "mood": mood,
                    "note": note
                }).execute()
                
                # if response.error:
                #     flash(f"Error tracking mood: {response.error.message}", "error")
                #     return redirect(url_for("track_mood"))
            
            flash("Moods tracked successfully!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            flash(f"Error tracking mood: {str(e)}", "error")
            return redirect(url_for("track_mood"))

@app.route("/my_moods")
@login_required
def my_moods():
    try:
        # Fetch moods from Supabase
        response = supabase.table("moods").select("*").eq("user_id", current_user.id).execute()
        mood_rows = response.data  # Extract the rows

        # Process and split combined moods
        all_moods = []
        for row in mood_rows:
            if row["mood"] and row["created_at"]:  # Ensure mood and created_at are not None
                # Split moods by comma and strip extra spaces
                moods = [m.strip() for m in row["mood"].split(",")]
                for mood in moods:
                    all_moods.append({"mood": mood, "created_at": row["created_at"]})

        return render_template("my_moods.html", all_moods=all_moods)
    except Exception as e:
        print("Error in my_moods route:", str(e))
        flash("Could not load mood data.", "error")
        return redirect(url_for("home"))

def fetch_all_moods_from_supabase():
    # Replace this with your actual Supabase fetching logic
    return supabase.table('moods').select('*').execute().data



if __name__ == "__main__":
    app.run(debug=True)
