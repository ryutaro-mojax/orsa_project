from flask import Flask, request, jsonify
from database import user_profiles #MongoDBコレクションをインポート
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os
from dotenv import load_dotenv  # dotenv をインポート

load_dotenv()  # .env ファイルをロード

app = Flask(__name__)

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

    data = request.json
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
@app.route("/orsa/user_profile", methods=["POST"])
def create_user_profile():
    try:
        data = request.json  # 送信データを取得
        user_id = data.get("user_id")
        
        # 必須フィールドチェック
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        # 保存データを作成
        user_data = {
            "user_id": user_id,
            "name": data.get("name", ""),
            "personality": data.get("personality", {}),
            "bazi_analysis": data.get("bazi_analysis", {}),
            "additional_analysis": data.get("additional_analysis", {}),
            "last_updated": datetime.datetime.utcnow().isoformat()
        }

        # MongoDB に保存
        result = user_profiles.insert_one(user_data)
        return jsonify({"message": "User profile saved", "id": str(result.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    app.run(debug=True)