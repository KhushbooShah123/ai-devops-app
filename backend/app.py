from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LAST
import time
import json
import threading
import queue
import os

app = Flask(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter('ai_worker_requests_total', 'Total AI Worker Requests')
CACHE_HIT_COUNT = Counter('ai_worker_cache_hits_total', 'Requests served from Cache')
QUEUE_TASKS_COUNT = Counter('ai_worker_queue_tasks_total', 'Tasks put in queue')
SCAN_TIME = Histogram('ai_worker_scan_time_seconds', 'Time taken for scanning')

# ==========================================
# PHASE 2: REAL REDIS (With Fallback)
# ==========================================
redis_client = None
USE_REAL_REDIS = False

try:
    import redis
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
    # Ping to check if really connected
    redis_client.ping()
    USE_REAL_REDIS = True
    print("✅ Connected to Real Redis!")
except Exception as e:
    print(f"⚠️ Real Redis not available, using In-Memory Fallback. Error: {e}")
    redis_client = None

# In-Memory Fallback Cache
IN_MEMORY_CACHE = {}

# ==========================================
# PHASE 3: IN-MEMORY QUEUE (Mock RabbitMQ)
# ==========================================
task_queue = queue.Queue()

def background_worker():
    while True:
        try:
            task_data = task_queue.get(timeout=1)
            task_id = task_data.get('task_id')
            print(f"[Background Worker] Starting AI Fix for task: {task_id}...")
            time.sleep(5) 
            print(f"[Background Worker] Completed AI Fix for task: {task_id}!")
            task_queue.task_done()
        except queue.Empty:
            pass

threading.Thread(target=background_worker, daemon=True).start()

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def home():
    redis_status = "Connected" if USE_REAL_REDIS else "Fallback (In-Memory)"
    return jsonify({"service": "AI-DevOps-Worker", "status": "Running", "redis_status": redis_status, "version": "v5-real-redis"})

@app.route('/health')
def health():
    """🆕 PRO ADDITION: Health Check Endpoint"""
    return jsonify({"status": "healthy", "redis": "up" if USE_REAL_REDIS else "down"}), 200

@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    REQUEST_COUNT.inc()
    data = request.json
    repo_url = data.get('repo_url', 'unknown')
    cache_key = f"scan:{repo_url}"

    # 1. CHECK CACHE (Real or Fallback)
    cache_data = None
    if USE_REAL_REDIS and redis_client:
        cached = redis_client.get(cache_key)
        if cached:
            CACHE_HIT_COUNT.inc()
            return jsonify({"source": "redis_cache", "data": json.loads(cached)}), 200
    elif cache_key in IN_MEMORY_CACHE:
        CACHE_HIT_COUNT.inc()
        return jsonify({"source": "in-memory_cache", "data": IN_MEMORY_CACHE[cache_key]}), 200

    # 2. DO HEAVY LIFTING
    with SCAN_TIME.time():
        time.sleep(1)
        result = {
            "repo_url": repo_url,
            "status": "success",
            "scores": {
                "docker_score": 85,
                "kubernetes_score": 90,
                "ci_cd_score": 75,
                "security_score": 88,
                "overall_production_readiness": 84
            },
            "fix_with_ai_available": True
        }

    # 3. SAVE TO CACHE
    json_result = json.dumps(result)
    if USE_REAL_REDIS and redis_client:
        redis_client.setex(cache_key, 3600, json_result) # Real Redis (1 hour)
    else:
        IN_MEMORY_CACHE[cache_key] = result # Fallback

    return jsonify({"source": "ai_fresh_scan", "data": result}), 200

@app.route('/api/fix', methods=['POST'])
def fix_code():
    QUEUE_TASKS_COUNT.inc()
    data = request.json
    task_id = f"fix-{int(time.time())}"
    task_queue.put({"task_id": task_id, "repo_url": data.get('repo_url')})
    return jsonify({"message": "AI Fix started!", "task_id": task_id, "status": "processing"}), 202

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LAST}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)