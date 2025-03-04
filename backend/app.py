from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# ✅ MongoDB接続
from pymongo import MongoClient
import os

# ✅ MONGO_URI を取得
mongo_uri = os.getenv("MONGO_URI")

# ✅ 明示的にオプションを設定して接続
client = MongoClient(
    mongo_uri,
    serverSelectionTimeoutMS=5000  # タイムアウト時間を設定
)

try:
    client.admin.command('ping')  # MongoDB に接続できるかテスト
    print("✅ MongoDB接続成功！")
except Exception as e:
    print(f"❌ MongoDB接続エラー: {e}")

# ✅ データベースとコレクションを取得
db = client["orsa_db"]
logs_collection = db["orsa_logs"]


# ✅ ログを記録する関数
def log_action(user_id, action):
    log_entry = {
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.utcnow(),
        "endpoint": request.endpoint  # 修正: endpointをrequest.endpointに変更
    }
    logs_collection.insert_one(log_entry)

# ✅ すべてのログを取得するエンドポイント
@app.route("/logs", methods=["GET"])
def get_logs():
    logs = list(logs_collection.find({}, {"_id": 0}))  # `_id` を除外して取得
    return jsonify(logs)

# ✅ ログを記録するエンドポイント
@app.route("/log", methods=["POST"])
def save_log():
    data = request.json
    if "user_id" in data and "action" in data:
        log_action(data["user_id"], data["action"])
        return jsonify({"message": "ログが記録されました"}), 201
    return jsonify({"error": "Invalid data"}), 400

from bson import ObjectId  # ObjectId をインポートする

# ✅ ログを更新するエンドポイント
@app.route("/log/<log_id>", methods=["PUT"])
def update_log(log_id):
    try:
        # 🟢 log_id を ObjectId に変換
        object_id = ObjectId(log_id)
    except:
        return jsonify({"error": "Invalid log_id format"}), 400  # ID が無効なら 400 エラー
    
    data = request.json
    update_fields = {}

    # 🟢 更新対象のフィールドを確認（他のフィールドも更新可能に）
    for key in ["action", "user_id", "timestamp"]:
        if key in data:
            update_fields[key] = data[key]

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    # 🟢 `_id` を ObjectId に変換して検索
    result = logs_collection.update_one({"_id": object_id}, {"$set": update_fields})

    if result.matched_count == 0:
        return jsonify({"error": "Log not found"}), 404

    return jsonify({"message": f"ログ {log_id} が更新されました"}), 200

from bson import ObjectId  # ObjectIdをインポート

# ✅ ログを削除するエンドポイント
@app.route("/log/<log_id>", methods=["DELETE"])
def delete_log(log_id):
    try:
        object_id = ObjectId(log_id)  # `log_id` を `ObjectId` に変換
    except:
        return jsonify({"error": "Invalid log_id format"}), 400  # 無効なID形式の場合

    result = logs_collection.delete_one({"_id": object_id})  # `ObjectId` で検索
    
    if result.deleted_count == 0:
        return jsonify({"error": "Log not found"}), 404

    return jsonify({"message": f"ログ {log_id} が削除されました"}), 200

# ✅ ユーザーアクション時に自動でログを記録するAPI
@app.route("/user_action", methods=["POST"])
def user_action():
    data = request.json
    if "user_id" in data and "action" in data:
        log_action(data["user_id"], data["action"])
        return jsonify({"message": f"ユーザー {data['user_id']} のアクション '{data['action']}' を記録しました"}), 201
    return jsonify({"error": "Invalid data"}), 400

@app.route("/")
def home():
    return "Hello, ORSA! This is the root endpoint."

import os
print("MONGO_URI from environment:", os.getenv("MONGO_URI"))


if __name__ == "__main__":
    app.run(debug=True)
