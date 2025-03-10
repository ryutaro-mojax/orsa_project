from flask import Flask, request, jsonify
from backend.database import user_profiles #MongoDBコレクションをインポート
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os
from dotenv import load_dotenv  # dotenv をインポート
from authlib.integrations.flask_client import OAuth # Google OAuthのライブラリ
from flask import redirect, url_for, session


load_dotenv()  # .env ファイルをロード

# Flaskアプリの作成
app = Flask(__name__)

# SECRET_KEY を環境変数から取得して設定
# Google OAuth 設定
oauth = OAuth(app)

app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")  # すでに追加済み

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



# 設定の読み込みと関数化
def get_mongo_client():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
        print("✅ MongoDB接続成功！")
    except Exception as e:
        print(f"❌ MongoDB接続エラー: {e}")
        raise  # 上位にエラーを伝播
    return client

# MongoDB 接続を初期化
try:
    client = get_mongo_client()
    db = client["orsa_db"]
# MongoDB コレクションを追加
    chat_history = db["chat_history"]
    logs_collection = db["orsa_logs"]
except ValueError as e:
    print(f"起動時エラー: {e}")
    # MongoDB接続に失敗した場合、アプリケーションを起動しないなどの対応も考えられます

# ログを記録する関数 (変更なし)
def log_action(user_id, action):
    log_entry = {
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.utcnow(),
        "endpoint": request.endpoint
    }
    logs_collection.insert_one(log_entry)

# すべてのログを取得するエンドポイント (変更なし)
@app.route("/logs", methods=["GET"])
def get_logs():
    logs = list(logs_collection.find({}, {"_id": 0}))
    return jsonify(logs)

# ログを記録するエンドポイント (入力データ検証を追加)
@app.route("/log", methods=["POST"])
def save_log():
    data = request.json
    if not data:
        return jsonify({"error": "リクエストボディが空です"}), 400
    if not isinstance(data.get("user_id"), str):
        return jsonify({"error": "user_id は文字列である必要があります"}), 400
    if not isinstance(data.get("action"), str):
        return jsonify({"error": "action は文字列である必要があります"}), 400
    if "user_id" in data and "action" in data:
        log_action(data["user_id"], data["action"])
        return jsonify({"message": "ログが記録されました"}), 201
    return jsonify({"error": "user_id と action が必須です"}), 400

# ログを更新するエンドポイント (入力データ検証とエラーハンドリングを強化)
@app.route("/log/<log_id>", methods=["PUT"])
def update_log(log_id):
    try:
        object_id = ObjectId(log_id)
    except:
        return jsonify({"error": "log_id の形式が無効です"}), 400

    data = request.get_json(force-True) #強制的にJSONとして扱う
    if not data:
        return jsonify({"error": "リクエストボディが空です"}), 400

    update_fields = {}
    for key, value in data.items():
        if key in ["action", "user_id"]: # 更新可能なフィールドを限定
            if not isinstance(value, str): # データ型検証
                return jsonify({"error": f"{key} は文字列である必要があります"}), 400
            update_fields[key] = value
        elif key == "timestamp": # timestamp の型検証 (ISO 8601形式を想定)
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00')) # 'Z' を '+00:00' に置換してパース
                update_fields[key] = value
            except ValueError:
                return jsonify({"error": "timestamp は ISO 8601 形式である必要があります"}), 400
        else:
            return jsonify({"error": f"更新できないフィールド {key} が指定されています"}), 400


    if not update_fields:
        return jsonify({"error": "更新する有効なフィールドがありません"}), 400

    try: # MongoDB の操作でエラーが発生した場合も捕捉
        result = logs_collection.update_one({"_id": object_id}, {"$set": update_fields})
        if result.matched_count == 0:
            return jsonify({"error": "ログが見つかりません"}), 404
        return jsonify({"message": f"ログ {log_id} が更新されました"}), 200
    except Exception as e:
        print(f"ログ更新エラー (log_id: {log_id}): {e}") # サーバーログにエラー詳細を出力
        return jsonify({"error": "ログ更新中にエラーが発生しました"}), 500 # 500 Internal Server Error


# ログを削除するエンドポイント (エラーハンドリングを強化)
@app.route("/log/<log_id>", methods=["DELETE"])
def delete_log(log_id):
    try:
        object_id = ObjectId(log_id)
    except:
        return jsonify({"error": "log_id の形式が無効です"}), 400

    try: # MongoDB の操作でエラーが発生した場合も捕捉
        result = logs_collection.delete_one({"_id": object_id})
        if result.deleted_count == 0:
            return jsonify({"error": "ログが見つかりません"}), 404
        return jsonify({"message": f"ログ {log_id} が削除されました"}), 200
    except Exception as e:
        print(f"ログ削除エラー (log_id: {log_id}): {e}") # サーバーログにエラー詳細を出力
        return jsonify({"error": "ログ削除中にエラーが発生しました"}), 500 # 500 Internal Server Error


# ユーザーアクション時に自動でログを記録するAPI (変更なし)
@app.route("/user_action", methods=["POST"])
def user_action():
    data = request.json
    if not data:
        return jsonify({"error": "リクエストボディが空です"}), 400
    if not isinstance(data.get("user_id"), str):
        return jsonify({"error": "user_id は文字列である必要があります"}), 400
    if not isinstance(data.get("action"), str):
        return jsonify({"error": "action は文字列である必要があります"}), 400
    if "user_id" in data and "action" in data:
        log_action(data["user_id"], data["action"])
        return jsonify({"message": f"ユーザー {data['user_id']} のアクション '{data['action']}' を記録しました"}), 201
    return jsonify({"error": "Invalid data"}), 400


@app.route("/")
def home():
    return "Hello, ORSA! This is the root endpoint."

print("MONGO_URI from environment:", os.getenv("MONGO_URI"))

# ✅ ユーザープロフィールを登録するAPI
import traceback  # エラー詳細を取得するため

@app.route("/orsa/user_profile", methods=["POST", "GET"])
def create_user_profile():
    try:
        print("✅ ユーザープロフィール作成リクエスト受信")
        print("リクエストヘッダー:", request.headers)
        print("リクエストボディ:", request.get_data(as_text=True))  # 受信したデータをそのまま表示

        # JSONとしてパース
        data = request.json
        if not data:
            print("❌ エラー: リクエストボディが空です")
            return jsonify({"error": "Request body is empty"}), 400

        user_id = data.get("user_id")

        if not user_id:
            print("❌ エラー: user_id がありません")
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
        print("✅ ユーザープロフィール作成成功:", result.inserted_id)

        return jsonify({"message": "User profile saved", "id": str(result.inserted_id)}), 201

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"❌ サーバーエラー発生: {error_msg}")  # 例外の詳細を出力
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

import openai

#✅ビックファイブ分析依頼
openai.api_key = os.getenv("OPENAI_API_KEY")  # 環境変数から取得

def analyze_personality(conversation):
    prompt = f"""
    次の会話履歴を分析し、ビッグファイブ性格診断のスコア（0.0〜1.0）を算出してください。
    会話:
    {conversation}

    解析結果は以下のJSONフォーマットで出力してください：
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
        messages=[{"role": "system", "content": "あなたは心理学者です。"},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

#✅四柱推命の計算依頼
from chinese_calendar import get_stem_branch  # 天干地支の計算ライブラリ

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


#✅会話履歴の取得と保存
@app.route("/chat-history", methods=["POST"])
def save_chat():
    try:
        data = request.json
        if not data or "user_id" not in data or "conversation" not in data:
            return jsonify({"error": "user_id and conversation are required"}), 400

        user_id = data["user_id"]
        conversation = data["conversation"]

        # 1️⃣ Chat GPTでビックファイブ解析
        analysis=analyze_personality(conversation)

            # 2️⃣ ユーザーの生年月日を取得して四柱推命を計算
         user = user_profiles.find_one({"user_id": user_id})
　　　　if not user：
    　　　　return jsonify({"error": "User not found"}), 404

　　　　birth_date = user.get("birth_date")
　　　　bazi_analysis = calculate_four_pillars(birth_date) if birth_date else {}

      
            # 3️⃣ データ保存
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
      


# Google OAuth ログインエンドポイント
@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

# Google OAuth コールバックエンドポイント
@app.route("/callback")
def callback():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token)
    
    # セッションに保存
    session["user"] = user_info

    return redirect(url_for("dashboard"))  # ログイン後の画面へリダイレクト


# ✅ ユーザープロフィールを取得するAPI
@app.route("/user_profile/<user_id>", methods=["GET"])
def get_user_profile(user_id):
    try:
        user_data = user_profiles.find_one({"user_id": user_id})
        
        if not user_data:
            return jsonify({"error": "User not found"}), 404

        # ObjectId を文字列に変換
        user_data["_id"] = str(user_data["_id"])

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ ルート一覧をログに出力（追加する部分）
print("Registered Routes:")
for rule in app.url_map.iter_rules():
    print(rule)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
    