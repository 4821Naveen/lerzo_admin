import os
import datetime
import re
from flask import Flask, render_template, request, redirect, url_for, session, flash

# Load environment variables
try:
    from dotenv import load_dotenv
    # Find .env relative to this file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
except ImportError:
    pass  # python-dotenv not installed, use system env vars

import requests

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("ADMIN_PANEL_SECRET", "change_this_secret")

# API Configuration - Use environment variables
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5001/api/admin")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_SECRET", "lerzo_admin_secret_key_2026")

def call_api(endpoint, method='GET', data=None):
    """Helper to call the main app's admin API."""
    url = f"{API_BASE_URL}/{endpoint.lstrip('/')}"
    headers = {
        'Authorization': f'Bearer {ADMIN_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    try:
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            response = requests.get(url, params=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"API Error {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}

@app.route("/")
def index():
    """Redirect home to dashboard if logged in, else login."""
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.errorhandler(404)
def not_found_error(e):
    return render_template("error.html", error="The requested page was not found."), 404

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler for all exceptions."""
    # Don't catch 404s here, let the 404 handler do it
    from werkzeug.exceptions import NotFound
    if isinstance(e, NotFound):
        return not_found_error(e)
        
    print(f"Error: {e}")
    return render_template("error.html", error=str(e)), 500
@app.before_request
def check_admin_auth():
    """Middleware to enforce admin authentication on all /admin routes."""
    # Since this app might be mounted at /admin or run as a standalone app,
    # we'll protect all routes except login and static.
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes:
        if not session.get("admin_logged_in"):
            return redirect(url_for('login'))


def login_required(func):
    """Protect routes to require admin authentication."""
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page using local .env credentials."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        # Admin credentials must come ONLY from .env
        env_user = os.getenv("ADMIN_USER", "admin")
        env_pass = os.getenv("ADMIN_PASS", "admin123")
        
        if username == env_user and password == env_pass:
            session.permanent = True
            session["admin_logged_in"] = True
            # Use our API token for all subsequent requests
            session["admin_token"] = ADMIN_API_TOKEN
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Clear admin session and redirect to login."""
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Render dashboard statistics via API."""
    result = call_api("dashboard")
    if not result.get("success"):
        return render_template("error.html", error=result.get("error")), 500
        
    return render_template(
        "dashboard.html", 
        stats=result.get("stats"),
        active_page="dashboard"
    )


@app.route("/users")
@login_required
def users():
    """List users via API."""
    name_query = request.args.get("name", "").strip()
    result = call_api("users", data={"name": name_query})
    
    if not result.get("success"):
        return render_template("error.html", error=result.get("error")), 500

    return render_template(
        "users.html",
        users=result.get("users"),
        filters={"name": name_query},
        active_page="users",
    )

@app.route("/subscriptions", methods=["GET", "POST"])
@login_required
def subscriptions():
    """Manage subscription plans via API."""
    if request.method == "POST":
        data = {
            "name": request.form.get("name"),
            "price": float(request.form.get("price", 0)),
            "duration_days": int(request.form.get("duration", 30))
        }
        result = call_api("subscriptions", "POST", data)
        if result.get("success"):
            flash("Subscription plan created!", "success")
        else:
            flash(result.get("error"), "danger")
            
    result = call_api("subscriptions")
    return render_template(
        "subscriptions.html", 
        plans=result.get("plans", []),
        active_page="subscriptions"
    )

@app.route("/api/search-users")
@login_required
def api_search_users():
    """API endpoint for live user search via main API."""
    q = request.args.get("q", "").strip()
    result = call_api("users", data={"name": q})
    return result if result.get("success") else {"users": []}

@app.route("/api-settings/razorpay", methods=["GET", "POST"])
@login_required
def razorpay_settings():
    """Manage Razorpay settings via API."""
    if request.method == "POST":
        data = {
            "razorpay_key_id": request.form.get("razorpay_key_id"),
            "razorpay_secret": request.form.get("razorpay_secret"),
            "webhook_secret": request.form.get("webhook_secret")
        }
        result = call_api("settings", "POST", data)
        if result.get("success"):
            flash("Settings updated!", "success")
        else:
            flash(result.get("error"), "danger")
            
    result = call_api("settings")
    return render_template("razorpay_settings.html", settings=result.get("settings", {}))

@app.route("/api-settings/google", methods=["GET", "POST"])
@login_required
def google_settings():
    """Manage Google settings via API."""
    if request.method == "POST":
        # Extract fields from form
        data = {
            "firebase_api_key": request.form.get("firebase_api_key"),
            "firebase_project_id": request.form.get("firebase_project_id"),
            "firebase_auth_domain": request.form.get("firebase_auth_domain"),
            "firebase_app_id": request.form.get("firebase_app_id"),
            "firebase_service_account": request.form.get("firebase_service_account"),
            "google_client_id": request.form.get("google_client_id"),
            "google_client_secret": request.form.get("google_client_secret")
        }
        
        # If raw config is provided, try to extract values (fallback for JS)
        raw_config = request.form.get("firebase_config_raw")
        if raw_config and raw_config.strip():
            try:
                # Basic extraction using regex for JS-style objects
                def extract(key):
                    match = re.search(f"{key}\\s*:\\s*['\"]([^'\"]+)['\"]", raw_config)
                    return match.group(1) if match else None
                
                if not data["firebase_api_key"]: data["firebase_api_key"] = extract("apiKey")
                if not data["firebase_project_id"]: data["firebase_project_id"] = extract("projectId")
                if not data["firebase_auth_domain"]: data["firebase_auth_domain"] = extract("authDomain")
                if not data["firebase_app_id"]: data["firebase_app_id"] = extract("appId")
            except: pass

        result = call_api("settings", "POST", data)
        if result.get("success"):
            flash("Settings updated!", "success")
        else:
            flash(result.get("error"), "danger")
            
    result = call_api("settings")
    return render_template("google_settings.html", settings=result.get("settings", {}))

@app.context_processor
def utility_processor():
    return {"current_year": datetime.date.today().year}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
