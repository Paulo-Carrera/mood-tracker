from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from dotenv import load_dotenv
from supabase import create_client, Client
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
    
    # Check if the response contains data
    if not response.data:
        print(f"Error loading user: {response}")
        return None  # No data or error
    
    user = response.data[0]  # Assuming user data is returned as a list
    return User(id=user["id"], email=user["email"], username=user.get("username"))

# Routes
@app.route("/")
@login_required  # Ensure user is logged in to view this page
def home():
    print(f"Current User: {current_user.username}")
    return render_template("index.html", username=current_user.username)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Retrieve form data
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")

        # Validate form data
        if not email or not password or not username:
            flash("Email, password, and username are required", "error")
            return redirect(url_for('register'))

        try:
            # Check if username or email already exists
            existing_user = supabase.table("users").select("*").eq("username", username).execute()
            existing_email = supabase.table("users").select("*").eq("email", email).execute()

            if existing_user.data:
                flash("Username already taken", "error")
                return redirect(url_for('register'))
            if existing_email.data:
                flash("Email already registered", "error")
                return redirect(url_for('register'))

            # Hash the password using Flask-Bcrypt
            hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

            # Insert the new user into the database
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
    if current_user.is_authenticated:  # If user is already logged in, redirect to home
        return redirect(url_for('home'))

    if request.method == "POST":
        data = request.form  # Use form data (not JSON)
        identifier = data.get("email") or data.get("username")  # Allow login with either email or username
        password = data.get("password")
        
        if not identifier or not password:
            flash("Email/Username and password are required", "error")
            return redirect(url_for('login'))
        
        # Fetch user by either email or username
        response = supabase.table("users").select("*").eq("email", identifier).execute()
        if not response.data:
            response = supabase.table("users").select("*").eq("username", identifier).execute()
        
        user = response.data
        if not user or not bcrypt.check_password_hash(user[0]["password"], password):
            flash("Invalid email/username or password", "error")
            return redirect(url_for('login'))
        
        # Log the user in
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

@app.route("/track_mood", methods=["POST"])
@login_required
def track_mood():
    # Access form data
    mood = request.form.get("mood")
    note = request.form.get("note", "")
    
    if not mood:
        flash("Mood is required", "error")
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

@app.route("/get_moods", methods=["GET"])
@login_required
def get_moods():
    try:
        response = supabase.table("moods").select("*").eq("user_id", current_user.id).execute()
        if response.error:
            return jsonify({"error": response.error.message}), 400
        return jsonify({"moods": response.data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
