"""
Locust load testing suite for Issue #24 Phase 3
3 scenarios: API Gateway, RAG Service, MCP Server
"""

from locust import HttpUser, TaskSet, task, between, constant_pacing, events
from locust.contrib.fasthttp import FastHttpUser
import json
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Scenario 1: API Gateway Load Testing
# ============================================================================

class APIGatewayTasks(TaskSet):
    """API Gateway chat completion tasks (70% chat, 20% models, 10% health)"""

    def on_start(self):
        """Initialize user session"""
        self.client.verify = False  # Skip SSL verification for local testing

    @task(7)
    def chat_completion(self):
        """POST /v1/chat/completions - Main API endpoint"""
        payload = {
            "model": "qwen2.5-14b-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": random.choice([
                        "Explain Python decorators",
                        "How do I optimize code for GPU?",
                        "What is the CAP theorem in distributed systems?",
                        "Design a rate limiter algorithm",
                        "Explain the actor model"
                    ])
                }
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }

        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Chat completion: {response.elapsed.total_seconds():.2f}s")
            else:
                response.failure(f"Status {response.status_code}: {response.text[:100]}")

    @task(2)
    def list_models(self):
        """GET /v1/models - Model listing endpoint"""
        with self.client.get("/v1/models", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def health_check(self):
        """GET /health - Health check endpoint"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")


class APIGatewayUser(FastHttpUser):
    """API Gateway load test user"""
    tasks = [APIGatewayTasks]
    wait_time = between(2, 5)  # 2-5 second think time


# ============================================================================
# Scenario 2: RAG Service Load Testing
# ============================================================================

class RAGServiceTasks(TaskSet):
    """RAG service tasks (70% query, 30% index)"""

    def on_start(self):
        """Initialize RAG user"""
        self.collection_name = f"collection_{random.randint(1, 10)}"
        self.client.verify = False

    @task(7)
    def query_rag(self):
        """POST /query - RAG query operation"""
        queries = [
            "How do I optimize Python code for GPU computing?",
            "Explain the benefits of using document retrieval",
            "What are best practices for microservices architecture?",
            "How does vector similarity search work?",
            "What is semantic search and why is it useful?"
        ]

        payload = {
            "query": random.choice(queries),
            "collection": self.collection_name,
            "top_k": 5
        }

        with self.client.post(
            "/query",
            json=payload,
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"RAG query: {response.elapsed.total_seconds():.2f}s")
            elif response.status_code == 503:
                # Expected for degraded service
                response.failure("Service degraded (503)")
            else:
                response.failure(f"Status {response.status_code}")

    @task(3)
    def index_documents(self):
        """POST /index - Document indexing"""
        payload = {
            "collection": self.collection_name,
            "path": "/app/documents"
        }

        with self.client.post(
            "/index",
            json=payload,
            catch_response=True,
            timeout=15
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 503:
                response.failure("Service degraded (503)")
            else:
                response.failure(f"Status {response.status_code}")


class RAGServiceUser(FastHttpUser):
    """RAG service load test user"""
    tasks = [RAGServiceTasks]
    wait_time = between(3, 8)  # 3-8 second think time


# ============================================================================
# Scenario 3: MCP Server Load Testing
# ============================================================================

class MCPServerTasks(TaskSet):
    """MCP server tasks (40% file ops, 40% git, 20% web)"""

    def on_start(self):
        """Initialize MCP user"""
        self.client.verify = False
        self.test_files = [
            "/mnt/e/worktree/issue-24/services/rag/app.py",
            "/mnt/e/worktree/issue-24/services/embedding/app.py",
            "/mnt/e/worktree/issue-24/Makefile"
        ]

    @task(4)
    def read_file(self):
        """MCP read_file tool"""
        file_path = random.choice(self.test_files)

        with self.client.post(
            "/execute",
            json={
                "tool": "read_file",
                "args": {"file_path": file_path}
            },
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def write_file(self):
        """MCP write_file tool"""
        with self.client.post(
            "/execute",
            json={
                "tool": "write_file",
                "args": {
                    "file_path": f"/tmp/test_load_{random.randint(1, 100)}.txt",
                    "content": f"Load test data {random.randint(1, 1000)}"
                }
            },
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(4)
    def git_status(self):
        """MCP git_status tool"""
        with self.client.post(
            "/execute",
            json={
                "tool": "git_status",
                "args": {"working_dir": "/mnt/e/worktree/issue-24"}
            },
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def git_log(self):
        """MCP git_log tool"""
        with self.client.post(
            "/execute",
            json={
                "tool": "git_log",
                "args": {
                    "working_dir": "/mnt/e/worktree/issue-24",
                    "max_count": 5
                }
            },
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def web_scrape(self):
        """MCP web_scrape tool"""
        urls = [
            "https://www.example.com",
            "https://www.python.org",
            "https://docs.python.org"
        ]

        with self.client.post(
            "/execute",
            json={
                "tool": "web_scrape",
                "args": {"url": random.choice(urls)}
            },
            catch_response=True,
            timeout=15
        ) as response:
            if response.status_code in [200, 503]:  # Accept success or degraded
                response.success()
            else:
                response.failure(f"Status {response.status_code}")


class MCPServerUser(FastHttpUser):
    """MCP server load test user"""
    tasks = [MCPServerTasks]
    wait_time = between(2, 6)  # 2-6 second think time


# ============================================================================
# Event Handlers for Monitoring
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    logger.info(f"Load test started")
    logger.info(f"Host: {environment.host}")
    logger.info(f"Scenarios configured: API Gateway, RAG Service, MCP Server")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    logger.info("Load test completed")
    logger.info(f"Total requests: {environment.stats.total.num_requests}")
    logger.info(f"Total failures: {environment.stats.total.num_failures}")
    logger.info(f"Average response time: {environment.stats.total.avg_response_time:.0f}ms")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response,
               context, exception, **kwargs):
    """Log detailed request information"""
    if exception:
        logger.warning(f"{request_type} {name}: {exception}")


# ============================================================================
# Configuration
# ============================================================================

if __name__ == "__main__":
    """
    Usage Examples:

    # Test Scenario 1: API Gateway (10 users)
    locust -f locustfile.py APIGatewayUser \
      --host http://localhost:8000 \
      --users 10 --spawn-rate 1 \
      --run-time 5m --headless

    # Test Scenario 2: RAG Service (5 users)
    locust -f locustfile.py RAGServiceUser \
      --host http://localhost:8002 \
      --users 5 --spawn-rate 1 \
      --run-time 5m --headless

    # Test Scenario 3: MCP Server (10 users)
    locust -f locustfile.py MCPServerUser \
      --host http://localhost:8020 \
      --users 10 --spawn-rate 1 \
      --run-time 5m --headless

    # Web UI (interactive)
    locust -f locustfile.py --host http://localhost:8000
    # Open: http://localhost:8089
    """
    pass
