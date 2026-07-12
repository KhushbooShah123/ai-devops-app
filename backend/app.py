from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
import json
import threading
import queue

app = Flask(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter('ai_worker_requests_total', 'Total AI Worker Requests')
CACHE_HIT_COUNT = Counter('ai_worker_cache_hits_total', 'Requests served from Cache')
QUEUE_TASKS_COUNT = Counter('ai_worker_queue_tasks_total', 'Tasks put in queue')
SCAN_TIME = Histogram('ai_worker_scan_time_seconds', 'Time taken for scanning')

# ==========================================
# PHASE 2: IN-MEMORY CACHE (Mock Redis)
# ==========================================
IN_MEMORY_CACHE = {}

# ==========================================
# PHASE 3: IN-MEMORY QUEUE (Mock RabbitMQ)
# ==========================================
task_queue = queue.Queue()

def background_worker():
    """Background thread that processes AI Fix tasks asynchronously"""
    while True:
        try:
            task_data = task_queue.get(timeout=1)
            task_id = task_data.get('task_id')
            print(f"[Background Worker] Starting AI Fix for task: {task_id}...")
            time.sleep(5) # Simulating Claude API taking 5 seconds
            print(f"[Background Worker] Completed AI Fix for task: {task_id}!")
            task_queue.task_done()
        except queue.Empty:
            pass

# Start the background thread when app starts
threading.Thread(target=background_worker, daemon=True).start()


# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def home():
    return jsonify({"service": "AI-DevOps-Worker", "status": "Running", "version": "v4-queue-mock-db"})

@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    REQUEST_COUNT.inc()
    data = request.json
    repo_url = data.get('repo_url', 'unknown')
    cache_key = f"scan:{repo_url}"

    # 1. CHECK CACHE (Mock Redis)
    if cache_key in IN_MEMORY_CACHE:
        CACHE_HIT_COUNT.inc()
        return jsonify({"source": "redis_cache", "data": IN_MEMORY_CACHE[cache_key]}), 200

    # 2. DO HEAVY LIFTING (AI Scan Simulation)
    with SCAN_TIME.time():
        time.sleep(1) # Simulating network/AI delay
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

    # 3. SAVE TO CACHE (Mock Redis/Postgres)
    IN_MEMORY_CACHE[cache_key] = result

    return jsonify({"source": "ai_fresh_scan", "data": result}), 200

@app.route('/api/fix', methods=['POST'])
def fix_code():
    """PHASE 3: Async Queue Endpoint"""
    QUEUE_TASKS_COUNT.inc()
    data = request.json
    task_id = f"fix-{int(time.time())}"
    
    # Put job in queue and return immediately (Don't wait for AI)
    task_queue.put({"task_id": task_id, "repo_url": data.get('repo_url')})
    
    # Frontend ko turant jawab do, background me kaam hoga
    return jsonify({"message": "AI Fix started!", "task_id": task_id, "status": "processing"}), 202

# Prometheus endpoint
@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)