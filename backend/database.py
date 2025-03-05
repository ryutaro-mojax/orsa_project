from pymongo import MongoClient
import os

# MongoDBの接続情報を環境変数から取得
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("❌ 環境変数 MONGO_URI が設定されていません！")

# MongoDBに接続
try:
    client = MongoClient(MONGO_URI)
    db = client["orsa_db"]  # データベース名
    user_profiles = db["user_profiles"]  # コレクション
    client.server_info()  # MongoDBに接続できるかテスト
    print("✅ MongoDB接続テスト成功")
except Exception as e:
    print(f"❌ MongoDB接続エラー: {e}")
    raise  # ここでエラーを明示的に発生させる


