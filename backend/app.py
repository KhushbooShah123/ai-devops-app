from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
import json
import threading
import queue
import os
import hashlib

app = Flask(__name__)

# ==========================================
# PROMETHEUS METRICS (Updated)
# ==========================================
REQUEST_COUNT = Counter('ai_worker_requests_total', 'Total AI Worker Requests')
CACHE_HIT_COUNT = Counter('ai_worker_cache_hits_total', 'Requests served from Cache')
CACHE_MISS_COUNT = Counter('ai_worker_cache_misses_total', 'Requests not found in cache')
QUEUE_TASKS_COUNT = Counter('ai_worker_queue_tasks_total', 'Tasks put in queue')
REQUEST_LATENCY = Histogram('ai_worker_request_latency_seconds', 'API request latency')


# ==========================================
# PHASE 2: REAL REDIS (With Fallback)
# ==========================================
redis_client = None

try:
    import redis

    redis_host = os.environ.get('REDIS_HOST', 'localhost')

    redis_client = redis.Redis(
        host=redis_host,
        port=6379,
        decode_responses=True
    )

    redis_client.ping()

    print("✅ Connected to Real Redis!")

except Exception as e:
    print(f"⚠️ Real Redis not available, using In-Memory Fallback. Error: {e}")
    redis_client = None


IN_MEMORY_CACHE = {}


# ==========================================
# PHASE 3: IN-MEMORY QUEUE
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


threading.Thread(
    target=background_worker,
    daemon=True
).start()


# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def home():

    redis_status = "Connected" if redis_client else "Fallback (In-Memory)"

    return jsonify({
        "service": "AI-DevOps-Worker",
        "status": "Running",
        "redis_status": redis_status,
        "version": "v6-production-grade"
    })


@app.route('/health')
def health():

    return jsonify({
        "status": "healthy",
        "redis": "up" if redis_client else "down"
    }), 200



@app.route('/api/analyze', methods=['POST'])
def analyze_repo():

    with REQUEST_LATENCY.time():

        REQUEST_COUNT.inc()

        data = request.get_json(silent=True)

        if not data or "repo_url" not in data:
            return jsonify({
                "error": "repo_url is required"
            }), 400


        repo_url = data["repo_url"]


        repo_hash = hashlib.md5(
            repo_url.encode()
        ).hexdigest()


        cache_key = f"scan:{repo_hash}"


        # CHECK CACHE

        if redis_client:

            cached = redis_client.get(cache_key)

            if cached:

                CACHE_HIT_COUNT.inc()

                return jsonify({
                    "source": "redis_cache",
                    "data": json.loads(cached)
                }), 200


        elif cache_key in IN_MEMORY_CACHE:

            CACHE_HIT_COUNT.inc()

            return jsonify({
                "source": "in-memory_cache",
                "data": IN_MEMORY_CACHE[cache_key]
            }), 200



        # CACHE MISS

        if redis_client:
            CACHE_MISS_COUNT.inc()



        # AI SCAN SIMULATION

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


        # SAVE CACHE

        json_result = json.dumps(result)


        cache_ttl = int(
            os.environ.get(
                "CACHE_TTL",
                "3600"
            )
        )


        if redis_client:

            redis_client.setex(
                cache_key,
                cache_ttl,
                json_result
            )

        else:

            IN_MEMORY_CACHE[cache_key] = result



        return jsonify({
            "source": "ai_fresh_scan",
            "data": result
        }), 200



@app.route('/api/fix', methods=['POST'])
def fix_code():

    QUEUE_TASKS_COUNT.inc()

    data = request.get_json(silent=True)

    task_id = f"fix-{int(time.time())}"


    task_queue.put({
        "task_id": task_id,
        "repo_url": data.get('repo_url')
    })


    return jsonify({
        "message": "AI Fix started!",
        "task_id": task_id,
        "status": "processing"
    }), 202



@app.route('/metrics')
def metrics():

    return generate_latest(), 200, {
        'Content-Type': CONTENT_TYPE_LATEST
    }



if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000
    )