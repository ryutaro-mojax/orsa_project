from flask import Flask, request, jsonify
from backend.database import user_profiles #MongoDB
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os
from dotenv import load_dotenv  # dotenv 
from authlib.integrations.flask_client import OAuth # Google OAuth
from flask import redirect, url_for, session


load_dotenv()  # .env 

# Flask
app = Flask(__name__)

# SECRET_KEY 
# Google OAuth 
oauth = OAuth(app)

app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")  # 

oauth.register(
    "google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    access_token_url="https://oauth2.googleapis.com/token",
    access_token_params=None,
    refresh_token_url=None,
    redirect_uri="http://orsa-project.onrender.com/callback",
    client_kwargs={"scope": "openid email profile"},
)



# 
def get_mongo_client():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
        print(" MongoDB")
    except Exception as e:
        print(f" MongoDB: {e}")
        raise  # 
    return client

# MongoDB 
try:
    client = get_mongo_client()
    db = client["orsa_db"]
# MongoDB 
    chat_history = db["chat_history"]
    logs_collection = db["orsa_logs"]
except ValueError as e:
    print(f": {e}")
    # MongoDB

#  ()
def log_action(user_id, action):
    log_entry = {
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.utcnow(),
        "endpoint": request.endpoint
    }
    logs_collection.insert_one(log_entry)

#  ()
@app.route("/logs", methods=["GET"])
def get_logs():
    logs = list(logs_collection.find({}, {"_id": 0}))
    return jsonify(logs)

#  ()
@app.route("/log", methods=["POST"])
def save_log():
    data = request.json
    if not data:
        return jsonify({"error": ""}), 400
    if not isinstance(data.get("user_id"), str):
        return jsonify({"error": "user_id "}), 400
    if not isinstance(data.get("action"), str):
        return jsonify({"error": "action "}), 400
    if "user_id" in data and "action" in data:
        log_action(data["user_id"], data["action"])
        return jsonify({"message": ""}), 201
    return jsonify({"error": "user_id  action "}), 400

#  ()
@app.route("/log/<log_id>", methods=["PUT"])
def update_log(log_id):
    try:
        object_id = ObjectId(log_id)
    except:
        return jsonify({"error": "log_id "}), 400

    data = request.get_json(force=True) #JSON
    if not data:
        return jsonify({"error": ""}), 400

    update_fields = {}
    for key, value in data.items():
        if key in ["action", "user_id"]: # 
            if not isinstance(value, str): # 
                return jsonify({"error": f"{key} "}), 400
            update_fields[key] = value
        elif key == "timestamp": # timestamp  (ISO 8601)
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00')) # 'Z'  '+00:00' 
                update_fields[key] = value
            except ValueError:
                return jsonify({"error": "timestamp  ISO 8601 "}), 400
        else:
            return jsonify({"error": f" {key} "}), 400


    if not update_fields:
        return jsonify({"error": ""}), 400

    try: # MongoDB 
        result = logs_collection.update_one({"_id": object_id}, {"$set": update_fields})
        if result.matched_count == 0:
            return jsonify({"error": ""}), 404
        return jsonify({"message": f" {log_id} "}), 200
    except Exception as e:
        print(f" (log_id: {log_id}): {e}") # 
        return jsonify({"error": ""}), 500 # 500 Internal Server Error


#  ()
@app.route("/log/<log_id>", methods=["DELETE"])
def delete_log(log_id):
    try:
        object_id = ObjectId(log_id)
    except:
        return jsonify({"error": "log_id "}), 400

    try: # MongoDB 
        result = logs_collection.delete_one({"_id": object_id})
        if result.deleted_count == 0:
            return jsonify({"error": ""}), 404
        return jsonify({"message": f" {log_id} "}), 200
    except Exception as e:
        print(f" (log_id: {log_id}): {e}") # 
        return jsonify({"error": ""}), 500 # 500 Internal Server Error


# API ()
@app.route("/user_action", methods=["POST"])
def user_action():
    data = request.json
    if not data:
        return jsonify({"error": ""}), 400
    if not isinstance(data.get("user_id"), str):
        return jsonify({"error": "user_id "}), 400
    if not isinstance(data.get("action"), str):
        return jsonify({"error": "action "}), 400
    if "user_id" in data and "action" in data:
        log_action(data["user_id"], data["action"])
        return jsonify({"message": f" {data['user_id']}  '{data['action']}' "}), 201
    return jsonify({"error": "Invalid data"}), 400


@app.route("/")
def home():
    return "Hello, ORSA! This is the root endpoint."

print("MONGO_URI from environment:", os.getenv("MONGO_URI"))

#  API
import traceback  # 

@app.route("/orsa/user_profile", methods=["POST", "GET"])
def create_user_profile():
    try:
        print(" ")
        print(":", request.headers)
        print(":", request.get_data(as_text=True))  # 

        # JSON
        data = request.json
        if not data:
            print(" : ")
            return jsonify({"error": "Request body is empty"}), 400

        user_id = data.get("user_id")

        if not user_id:
            print(" : user_id ")
            return jsonify({"error": "user_id is required"}), 400

        user_data = {
            "user_id": user_id,
            "name": data.get("name", ""),
            "personality": data.get("personality", {}),
            "bazi_analysis": data.get("bazi_analysis", {}),
            "additional_analysis": data.get("additional_analysis", {}),
            "last_updated": datetime.utcnow().isoformat()
        }

        result = user_profiles.insert_one(user_data)
        print(" :", result.inserted_id)

        return jsonify({"message": "User profile saved", "id": str(result.inserted_id)}), 201

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f" : {error_msg}")  # 
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

import openai

#
openai.api_key = os.getenv("OPENAI_API_KEY")  # 

def analyze_personality(conversation):
    prompt = f"""
    0.01.0
    :
    {conversation}

    JSON
    {{
      "openness": 0.85,
      "conscientiousness": 0.65,
      "extraversion": 0.40,
      "agreeableness": 0.70,
      "neuroticism": 0.45
    }}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": ""},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

#
from chinese_calendar import get_stem_branch  # 

def calculate_four_pillars(birth_date):
    try:
        birth_year, birth_month, birth_day = map(int, birth_date.split("-"))
        year_pillar = get_stem_branch(birth_year)
        month_pillar = get_stem_branch(birth_month)
        day_pillar = get_stem_branch(birth_day)

        return {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
        }
    except Exception as e:
        return {"error": str(e)}


#
@app.route("/chat-history", methods=["POST"])
def save_chat():
    try:
        data = request.json
        if not data or "user_id" not in data or "conversation" not in data:
            return jsonify({"error": "user_id and conversation are required"}), 400

        user_id = data["user_id"]
        conversation = data["conversation"]

        # 1 Chat GPT
        analysis=analyze_personality(conversation)

             # 2 
        user=user_profiles.find_one({"user_id":user_id})
        if not user:
            return jonify({"error":User not found"}),404

        birth_data=user.get("birth_date")
        bazi_analysis=calculate_four_pillars(birth_date)if birth_date else{}
      
            # 3 
        chat_entry = {
             "user_id": user_id,
          "timestamp": datetime.utcnow().isoformat(),
          "conversation": conversation,
          "analysis": {
              "big_five": analysis,
              "four_pillars": bazi_analysis
          }
       }

      chat_history.insert_one(chat_entry)
      return jsonify({"message": "Chat saved", "analysis": chat_entry["analysis"]}), 201

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
      


# Google OAuth 
@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

# Google OAuth 
@app.route("/callback")
def callback():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token)
    
    # 
    session["user"] = user_info

    return redirect(url_for("dashboard"))  # 


#  API
@app.route("/user_profile/<user_id>", methods=["GET"])
def get_user_profile(user_id):
    try:
        user_data = user_profiles.find_one({"user_id": user_id})
        
        if not user_data:
            return jsonify({"error": "User not found"}), 404

        # ObjectId 
        user_data["_id"] = str(user_data["_id"])

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#  
print("Registered Routes:")
for rule in app.url_map.iter_rules():
    print(rule)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
    