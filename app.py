from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from supabase import Client, create_client
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import requests
from email.mime.multipart import MIMEMultipart
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import openai
import random
# Load environment variables
load_dotenv(dotenv_path=".env")


app = Flask(__name__)
app.secret_key = os.getenv("app.secret_key")
#openai_api_key = os.getenv("OPENAI_API_KEYY")
#client = OpenAI(api_key=openai_api_key)
# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")
# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
DEMO_MODE= True

# ----------------- Routes -----------------
@app.route("/signup-page")
def signup_page():
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()  # remove all session data
    return redirect(url_for("home"))  

@app.route("/login-page")
def login_page():
    return render_template("login.html")

@app.route('/')
def home():
    return render_template('home.html')

@app.route("/register-restaurant")
def register_restaurant_page():
    return render_template("register_restaurant.html")

@app.route("/search-diners")
def search_diners_page():
    return render_template("search_diners.html")

# ----------------- Dashboard route -----------------
@app.route("/dashboard")
def dashboard():
    restaurant = None
    user_id = request.args.get("user_id")
    restaurant_id = request.args.get("restaurant_id")
    if restaurant_id:
        resp = supabase.table("restaurants").select("*").eq("id", restaurant_id).execute()
        if resp.data:
            restaurant = resp.data[0]
    elif user_id:
        resp = supabase.table("restaurants").select("*").eq("user_id", user_id).execute()
        if resp.data:
            restaurant = resp.data[0]

    return render_template("dashboard.html", restaurant=restaurant)

    # If coming from login (use user_id to find restaurant)
    user_id = request.args.get("user_id")
    if user_id and not restaurant:
        response = supabase.table("restaurants").select("*").eq("user_id", user_id).execute()
        if response.data:
            restaurant = response.data[0]

    return render_template("dashboard.html", restaurant=restaurant)


# ----------------- Sign-up route -----------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    password_hash = generate_password_hash(password)

    try:
        # Insert user
        supabase.table("users").insert({
            "email": email,
            "password_hash": password_hash
        }).execute()

        # Fetch the newly created user to get the id
        response = supabase.table("users").select("id").eq("email", email).execute()
        user_id = response.data[0]["id"]

        return jsonify({
            "message": "User registered successfully",
            "user_id": user_id
        }), 201

    except Exception as e:
        # Check if it’s a duplicate email error
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify({"error": "This email is already registered."}), 409
        return jsonify({"error": str(e)}), 500

# ----------------- Login route -----------------
@app.route("/login-api", methods=["POST"])
def login_api():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user_response = supabase.table("users").select("*").eq("email", email).execute()
    if not user_response.data:
        return jsonify({"error": "Invalid email or password"}), 401

    user = user_response.data[0]
    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    # Only return the user_id, no message
    return jsonify({"user_id": user["id"]})

# ----------------- Register Restaurant API route -----------------
@app.route("/register-restaurant-api", methods=["POST"])
def register_restaurant_api():
    data = request.get_json()
    user_id = data.get("user_id")
    name = data.get("name")
    cuisine = data.get("cuisine")
    location = data.get("location")

    response = supabase.table("restaurants").insert({
        "user_id": user_id,
        "name": name,
        "cuisine": cuisine,
        "location": location
    }).execute()

    restaurant = response.data[0] if response.data else None

    return jsonify({
        "message": "Restaurant registered successfully!",
        "restaurant_id": restaurant["id"] if restaurant else None
    })

# ----------------- Generate AI Offer route -----------------

# Demo diners list
DINERS = [
    "alice@example.com",
    "bob@example.com",
    "carol@example.com"
]

@app.route("/generate-ai-offer", methods=["POST"])
def generate_ai_offer():
    data = request.get_json()
    title = data.get("title", "Special Offer")
    end_date = data.get("end_date", "")
    restaurant_id = data.get("restaurant_id")

    # Get restaurant name
    restaurant_name = "Your Restaurant"
    if restaurant_id:
        resp = supabase.table("restaurants").select("name").eq("id", restaurant_id).execute()
        if resp.data and resp.data[0].get("name"):
            restaurant_name = resp.data[0]["name"]

    # Format the date nicely
    try:
        formatted_date = datetime.strptime(end_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except:
        formatted_date = end_date

    # DEMO_MODE: generate local AI message
    if DEMO_MODE:
        templates = [
            f"🎉 Hey foodies! {restaurant_name} is serving up '{title}' until {formatted_date}. Don’t miss out! 🍽️",
            f"🔥 Hot deal alert! '{title}' at {restaurant_name} – grab it before {formatted_date}!",
            f"🥳 Time to treat yourself! Enjoy '{title}' at {restaurant_name} before {formatted_date}.",
            f"🍕 Delicious deal incoming! '{title}' at {restaurant_name} is available until {formatted_date}. Bring your friends!"
        ]
        ai_message = random.choice(templates)
        #print(f"[DEMO MODE] Generated AI offer: {ai_message}")
    else:
        # real OpenAI API call (if you disable demo mode)
        try:
            prompt = f"Write a fun and creative restaurant promotion. Restaurant: '{restaurant_name}', Special Offer: '{title}', ends on {formatted_date}. Make it engaging and persuasive."
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a creative marketing assistant for restaurants."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.8
            )
            ai_message = response.choices[0].message.content.strip()
        except Exception as e:
            print("OpenAI API error:", e)
            ai_message = f"{restaurant_name} has a special offer: '{title}', valid until {formatted_date}."

    return jsonify({"message": ai_message, "restaurant_name": restaurant_name})


# ----------------- Users route -----------------
@app.route("/users")
def get_users():
    try:
        response = supabase.table("users").select("*").limit(5).execute()
        if not response.data:
            return jsonify({"message": "No users found"}), 200
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------- Restaurants route -----------------
@app.route("/restaurants")
def get_restaurants():
    try:
        response = supabase.table("restaurants").select("*").limit(5).execute()
        if not response.data:
            return jsonify({"message": "No restaurants found"}), 200
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------- Diners route -----------------
@app.route("/diners")
def get_diners():
    try:
        response = supabase.table("diners").select("*").limit(5).execute()
        if not response.data:
            return jsonify({"message": "No diners found"}), 200
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------- Offers route -----------------
@app.route("/offers")
def get_offers():
    try:
        response = supabase.table("offers").select("*").limit(5).execute()
        if not response.data:
            return jsonify({"message": "No offers found"}), 200
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------- Search Diners json route -----------------
@app.route("/search-diners-json")
def search_diners_json():
    city = request.args.get("city")
    state = request.args.get("state")
    type_filter = request.args.get("type")

    # Start Supabase query
    query = supabase.table("diners").select("*")

    # Filter by city
    if city:
        query = query.ilike("city", f"%{city}%")
    
    # Filter by state
    if state:
        query = query.ilike("state", f"%{state}%")
    
    # Filter by dining interests (partial match in comma-separated string)
    if type_filter:
        query = query.ilike("dining_interests", f"%{type_filter}%")

    # Execute query
    response = query.execute()
    diners = response.data if response.data else []

    # Construct full name safely
    for d in diners:
        d["name"] = f"{d.get('first_name') or ''} {d.get('last_name') or ''}".strip()
        if not d["name"]:
            d["name"] = d.get("email")  # fallback to email if name missing

        # Ensure dining_interests is not None
        if not d.get("dining_interests"):
            d["dining_interests"] = ""

    return jsonify(diners)

# ----------------- Send Offer route -----------------
@app.route('/send-offer', methods=['POST'])
def send_offer():
    data = request.json or {}
    offer_text = data.get("offer")
    offer_title = data.get("title", "Special Offer")
    offer_message = data.get("message", "")
    restaurant_id = data.get("restaurant_id") or session.get("restaurant_id")
    restaurant_name = data.get("restaurant_name", "Your Restaurant")  # optional
    selected_diners = data.get("recipients", []) 

    # Validate required fields
    if not restaurant_id:
        return jsonify({"success": False, "error": "Restaurant ID missing"}), 400
    if not offer_title or not offer_message or len(selected_diners) == 0:
        return jsonify({"success": False, "error": "Please fill all fields and select diners"}), 400

    try:
        recipient_count = len(selected_diners)
        # Save offer to Supabase
        offer_resp = supabase.table("offers").insert({
            "restaurant_id": restaurant_id,
            "title": offer_title,
            "message": offer_message,
            "recipient_count": recipient_count,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        offer = offer_resp.data[0] if offer_resp.data else None
 
        if DEMO_MODE:
            for recipient in selected_diners:
                print(f"[DEMO MODE] Would send email to {recipient} with message: {offer_message}")
        else:
            try:
                smtp_server = smtplib.SMTP("smtp.gmail.com", 587)
                smtp_server.starttls()
                smtp_server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
                for recipient in selected_diners:
                    msg = MIMEMultipart()
                    msg['From'] = GMAIL_EMAIL
                    msg['To'] = recipient
                    msg['Subject'] = f"{restaurant_name} - {offer_title}"
                    msg.attach(MIMEText(offer_message, 'plain'))
                    smtp_server.sendmail(GMAIL_EMAIL, recipient, msg.as_string())
                smtp_server.quit()
                print(f"Offer emails sent to {recipient_count} diners.")
            except Exception as e:
                print("Error sending emails:", e)

        return jsonify({
            "success": True,
            "message": "Offer saved successfully! (Emails sent in live mode)",
            "offer": offer
        })

    except Exception as e:
        print("Error saving offer:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------- Offers Restaurant route -----------------
@app.route("/offers/<restaurant_id>")
def get_offers_by_restaurant(restaurant_id):
    try:
        response = supabase.table("offers") \
            .select("id, title, created_at, recipient_count") \
            .eq("restaurant_id", restaurant_id) \
            .order("created_at", desc=True) \
            .execute()

        offers = response.data if response.data else []
        return jsonify(offers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------- Offer Recipients route -----------------
@app.route("/offer_recipients")
def get_offer_recipients():
    try:
        response = supabase.table("offer_recipients").select("*").limit(5).execute()
        if not response.data:
            return jsonify({"message": "No offer recipients found"}), 200
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------- Cities by state route -----------------
@app.route("/cities-by-state")
def cities_by_state():
    state = request.args.get("state")
    if not state:
        return jsonify([])

    try:
        # Query diners where state matches exactly (case-insensitive)
        response = supabase.table("diners").select("city").ilike("state", state).execute()
        
        # Extract unique, non-empty cities
        cities = sorted(list({d["city"] for d in response.data if d.get("city")})) if response.data else []
        return jsonify(cities)
    
    except Exception as e:
        print("Error fetching cities:", e)
        return jsonify([])




if __name__ == "__main__":
    app.run(debug=True)
