# Security Module Dependencies Map

## Module Dependency Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         app.py (FastAPI)                    │
│                     MCP Server Main Entry                    │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴─────────────────┐
        │                          │
        ▼                          ▼
┌───────────────┐          ┌──────────────────┐
│  Middleware   │          │   MCP Tools      │
│               │          │   (@mcp.tool())  │
└───────┬───────┘          └────────┬─────────┘
        │                           │
        │                           │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   RBAC Middleware     │◄───── settings.py
        │  (rbac_middleware.py) │
        └───────────┬───────────┘
                    │
        ┌───────────┴────────────┐
        │                        │
        ▼                        ▼
┌───────────────┐        ┌──────────────────┐
│  RBAC Manager │        │  Audit Logger    │
│ (rbac.py)     │        │ (audit_logger.py)│
└───────┬───────┘        └────────┬─────────┘
        │                         │
        │                         │
        ▼                         ▼
┌───────────────────┐     ┌──────────────────┐
│ Security Database │     │ Security Database│
│ (security_db.py)  │     │ (security_db.py) │
└────────┬──────────┘     └────────┬─────────┘
         │                         │
         └─────────┬───────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │   SQLite Database   │
         │   (security.db)     │
         │   - WAL Mode        │
         └─────────────────────┘
```

## Existing Security Modules (Already Implemented)

### 1. security.py
**Purpose**: AST-based code validation and secure execution

**Dependencies**:
- Python `ast` module
- `sandbox.py` (for containerized execution)

**Used By**:
- `app.py` - `execute_python` tool

**Key Functions**:
- `get_security_validator()`: Returns SecurityValidator instance
- `get_secure_executor()`: Returns SecureExecutor instance
- `SecurityValidator.validate_code()`: AST-based validation
- `SecureExecutor.execute_python_code()`: Secure code execution

### 2. sandbox.py
**Purpose**: Docker container-based sandboxing

**Dependencies**:
- Docker runtime
- `logging` module

**Used By**:
- `security.py` - SecureExecutor
- `app.py` - direct usage for Python execution

**Key Classes**:
- `ContainerSandbox`: Docker container executor
- `SandboxLogger`: Audit logging to file
- `SessionManager`: Session-based violation tracking

**Resource Limits**:
- Memory: 512MB
- CPU Timeout: 30s
- Max Processes: 10
- Network: Isolated
- Filesystem: Read-only + tmpfs

### 3. rate_limiter.py
**Purpose**: Rate limiting and concurrent execution control

**Dependencies**:
- `threading` module
- `time` module

**Used By**:
- `app.py` - `/tools/{tool_name}/call` endpoint

**Key Classes**:
- `RateLimiter`: Per-tool rate limiting
- `AccessControl`: Tool sensitivity classification

**Tool Sensitivity Levels**:
- LOW: read_file, list_files
- MEDIUM: execute_bash, git_*
- HIGH: write_file, execute_python
- CRITICAL: (reserved for future)

### 4. safe_api.py
**Purpose**: Path traversal prevention and safe file operations

**Dependencies**:
- `pathlib` module
- `security.py` (SecurityError)

**Used By**:
- `app.py` - read_file, write_file, list_files tools

**Key Functions**:
- `secure_resolve_path()`: Path validation
- `SafeFileAPI.read_text()`: Safe file reading
- `SafeFileAPI.write_text()`: Safe file writing
- `SafeCommandExecutor.execute_command()`: Safe command execution

**Blocked Paths**:
- `/etc/*`, `/root/*`, `/sys/*`, `/proc/*`
- `C:\\Windows\\*`, `C:\\Program Files\\*`
- `/etc/passwd`, `/etc/shadow`, SAM, SECURITY

### 5. security_admin.py
**Purpose**: Security administration API

**Dependencies**:
- FastAPI
- `rate_limiter.py`
- `sandbox.py`

**Endpoints**:
- `GET /admin/security/config`: Get security configuration
- `GET /admin/security/sessions`: List active sessions
- `POST /admin/security/sessions/{session_id}/reset`: Reset session violations

## New Modules to Implement (Issue #8)

### Phase 1: Database Layer

#### 1. security_database.py
**Purpose**: SQLite CRUD operations and connection pooling

**Dependencies**:
- `aiosqlite`
- `settings.py`

**Will Be Used By**:
- `rbac_manager.py`
- `audit_logger.py`

**Key Functions**:
```python
async def init_database() -> None
async def get_user(user_id: str) -> Optional[Dict]
async def get_role_permissions(role_id: int) -> List[Dict]
async def insert_audit_log(log_entry: Dict) -> int
async def check_permission(user_id: str, permission: str) -> bool
```

**Schema Tables**:
- `security_users`
- `security_roles`
- `security_permissions`
- `security_role_permissions`
- `security_audit_logs`

#### 2. seed_security_data.py
**Purpose**: Initial data population script

**Dependencies**:
- `security_database.py`

**Actions**:
- Create default roles (guest, developer, admin)
- Create default permissions (18 MCP tools)
- Map role-permission relationships

### Phase 2: RBAC Layer

#### 3. rbac_manager.py
**Purpose**: Role-permission lookup and caching

**Dependencies**:
- `security_database.py`
- `settings.py`

**Will Be Used By**:
- `rbac_middleware.py`

**Key Functions**:
```python
async def check_permission(user_id: str, tool_name: str) -> Tuple[bool, str]
async def get_user_role(user_id: str) -> Optional[str]
async def cache_permissions(user_id: str) -> None
```

**Caching Strategy**:
- TTL: 5 minutes
- Invalidation: On role change or permission update

#### 4. rbac_middleware.py
**Purpose**: FastAPI middleware for automatic permission checking

**Dependencies**:
- FastAPI
- `rbac_manager.py`
- `audit_logger.py`

**Will Be Used By**:
- `app.py` - registered as middleware

**Flow**:
```
1. Extract user_id from request header
2. Extract tool_name from URL path
3. Check RBAC permission
4. If denied -> Log & Return 403
5. If allowed -> Pass to next handler
```

### Phase 3: Audit Logging Layer

#### 5. audit_logger.py
**Purpose**: Asynchronous audit logging with queue

**Dependencies**:
- `aiosqlite`
- `asyncio.Queue`
- `security_database.py`

**Will Be Used By**:
- `rbac_middleware.py`
- `sandbox.py` (integration)

**Key Features**:
- Non-blocking async logging (<5ms)
- Batch insertion (configurable)
- Queue overflow handling
- Automatic log partitioning (monthly tables)

**Log Entry Fields**:
- user_id, tool_name, action, status
- error_message, timestamp, execution_time_ms

## Initialization Sequence

### Startup Order

```
1. settings.py          - Load environment variables
2. security_database.py - Initialize SQLite DB (WAL mode)
3. rbac_manager.py      - Load permissions into cache
4. audit_logger.py      - Start async writer task
5. rbac_middleware.py   - Register FastAPI middleware
6. app.py               - Start MCP server
```

### Initialization Code (app.py)

```python
from settings import settings
from security_database import init_database
from rbac_manager import get_rbac_manager
from audit_logger import get_audit_logger
from rbac_middleware import RBACMiddleware

async def startup_event():
    # Validate configuration
    warnings = settings.validate_config()
    for warning in warnings:
        logger.warning(warning)

    # Initialize database
    if settings.is_rbac_enabled():
        await init_database()
        logger.info(f"Security DB initialized: {settings.get_db_path()}")

        # Prewarm RBAC cache
        rbac_manager = get_rbac_manager()
        await rbac_manager.prewarm_cache()

        # Start audit logger
        audit_logger = get_audit_logger()
        audit_logger.start_async_writer()

    # Register RBAC middleware
    if settings.is_rbac_enabled():
        app.add_middleware(RBACMiddleware)

app.add_event_handler("startup", startup_event)
```

## Module Interaction Flow

### Example: execute_python Tool Call with RBAC

```
User Request
    ↓
FastAPI (app.py)
    ↓
CORSMiddleware
    ↓
RBACMiddleware
    ├→ Extract user_id from header
    ├→ Extract tool_name = "execute_python"
    ├→ Call rbac_manager.check_permission(user_id, "execute_python")
    │   ├→ Check cache
    │   └→ If miss: Query security_database
    ├→ If denied:
    │   ├→ Call audit_logger.log_denied(user_id, tool_name)
    │   └→ Return HTTP 403
    └→ If allowed: Continue
    ↓
RateLimiter Middleware
    ├→ Check rate limit
    └→ Check concurrent execution limit
    ↓
MCP Tool Handler (@mcp.tool)
    ├→ Call security_validator.validate_code()
    └→ Call secure_executor.execute_python_code()
        ├→ ContainerSandbox.run()
        └→ SandboxLogger.log_execution()
    ↓
AuditLogger
    └→ Log success/failure
    ↓
Response to User
```

## Performance Targets

| Component | Target Latency (p95) |
|-----------|---------------------|
| RBAC Permission Check | <10ms |
| Audit Logging (async) | <5ms |
| Sandbox Overhead | <100ms |
| Total Request Time | <500ms |

## Rollback Strategy

### Feature Flags
- `RBAC_ENABLED=false` - Disable RBAC, use legacy mode
- `SANDBOX_ENABLED=false` - Disable Docker sandbox, use process isolation
- `RATE_LIMIT_ENABLED=false` - Disable rate limiting

### Graceful Degradation
- If RBAC DB unavailable: Log warning, allow all requests
- If Audit logging fails: Log error, continue request processing
- If Sandbox fails: Fallback to process-based execution

## Testing Dependencies

Each module should have corresponding test file:
- `test_settings.py` - Test environment variable loading
- `test_security_database.py` - Test CRUD operations
- `test_rbac_manager.py` - Test permission checking
- `test_audit_logger.py` - Test async logging
- `test_rbac_middleware.py` - Test middleware integration

Integration tests should cover:
- Full request flow with RBAC enabled
- WAL mode concurrent access (10+ connections)
- Failure scenarios and rollback behavior
