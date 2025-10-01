# Security Architecture Design

## Entity Relationship Diagram (ERD)

### Database Schema

```mermaid
erDiagram
    security_users ||--o{ security_roles : has
    security_roles ||--o{ security_role_permissions : has
    security_permissions ||--o{ security_role_permissions : has
    security_users ||--o{ security_audit_logs : generates

    security_users {
        text user_id PK
        text username
        int role_id FK
        text created_at
    }

    security_roles {
        int role_id PK
        text role_name UK
        text description
    }

    security_permissions {
        int permission_id PK
        text permission_name UK
        text resource_type
        text action
    }

    security_role_permissions {
        int role_id PK_FK
        int permission_id PK_FK
    }

    security_audit_logs {
        int log_id PK
        text user_id FK
        text tool_name
        text action
        text status
        text error_message
        text timestamp
        int execution_time_ms
    }
```

### Table Details

#### security_users
**Purpose**: Store user information and role assignments

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| user_id | TEXT | PRIMARY KEY | Unique user identifier |
| username | TEXT | NOT NULL | Display name |
| role_id | INTEGER | FOREIGN KEY | Reference to security_roles |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP | Account creation time |

**Indexes**:
- Primary: user_id
- Foreign: role_id → security_roles(role_id)

#### security_roles
**Purpose**: Define available roles (guest, developer, admin)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| role_id | INTEGER | PRIMARY KEY AUTOINCREMENT | Role identifier |
| role_name | TEXT | NOT NULL UNIQUE | Role name (guest/developer/admin) |
| description | TEXT | NULL | Role description |

**Default Roles**:
- `guest` (role_id=1): Read-only access
- `developer` (role_id=2): Developer access with code execution
- `admin` (role_id=3): Full administrative access

#### security_permissions
**Purpose**: Define granular permissions for MCP tools

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| permission_id | INTEGER | PRIMARY KEY AUTOINCREMENT | Permission identifier |
| permission_name | TEXT | NOT NULL UNIQUE | Permission name (matches tool name) |
| resource_type | TEXT | NULL | Resource type (tool/file/system) |
| action | TEXT | NULL | Action type (read/write/execute) |

**Examples**:
- `read_file` - resource_type: file, action: read
- `execute_python` - resource_type: tool, action: execute
- `git_commit` - resource_type: tool, action: execute

#### security_role_permissions
**Purpose**: Map roles to permissions (many-to-many)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| role_id | INTEGER | PK, FK | Reference to security_roles |
| permission_id | INTEGER | PK, FK | Reference to security_permissions |

**Composite Primary Key**: (role_id, permission_id)

**Cascading Rules**:
- ON DELETE CASCADE: Deleting role removes all mappings
- ON DELETE CASCADE: Deleting permission removes all mappings

#### security_audit_logs
**Purpose**: Record all tool invocations and security events

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| log_id | INTEGER | PRIMARY KEY AUTOINCREMENT | Log entry identifier |
| user_id | TEXT | NULL | User who invoked the tool |
| tool_name | TEXT | NULL | MCP tool name |
| action | TEXT | NULL | Action performed |
| status | TEXT | NULL | Result (success/denied/error) |
| error_message | TEXT | NULL | Error details if failed |
| timestamp | TEXT | DEFAULT CURRENT_TIMESTAMP | Event timestamp |
| execution_time_ms | INTEGER | NULL | Execution duration in milliseconds |

**Indexes**:
- Primary: log_id
- Index: user_id (for user activity queries)
- Index: tool_name (for tool usage statistics)
- Index: timestamp (for time-based queries)

---

## Sequence Diagrams

### 1. RBAC Permission Check Flow

```mermaid
sequenceDiagram
    participant User
    participant FastAPI
    participant RBACMiddleware
    participant RBACManager
    participant SecurityDB
    participant AuditLogger
    participant MCPTool

    User->>FastAPI: POST /tools/execute_python
    FastAPI->>RBACMiddleware: Request with user_id header

    alt RBAC Enabled
        RBACMiddleware->>RBACMiddleware: Extract user_id from header
        RBACMiddleware->>RBACMiddleware: Extract tool_name from URL

        RBACMiddleware->>RBACManager: check_permission(user_id, "execute_python")

        alt Cache Hit
            RBACManager->>RBACManager: Get from cache
            RBACManager-->>RBACMiddleware: (allowed, reason)
        else Cache Miss
            RBACManager->>SecurityDB: SELECT permissions for user
            SecurityDB-->>RBACManager: permission_list
            RBACManager->>RBACManager: Update cache
            RBACManager-->>RBACMiddleware: (allowed, reason)
        end

        alt Permission Denied
            RBACMiddleware->>AuditLogger: log_denied(user_id, tool_name)
            AuditLogger->>SecurityDB: INSERT INTO audit_logs (async)
            RBACMiddleware-->>FastAPI: HTTP 403 Forbidden
            FastAPI-->>User: {"error": "Permission denied"}
        else Permission Allowed
            RBACMiddleware->>FastAPI: Continue to next handler
            FastAPI->>MCPTool: execute_python(code)
            MCPTool->>MCPTool: Run in sandbox
            MCPTool-->>FastAPI: Result
            FastAPI->>AuditLogger: log_success(user_id, tool_name, exec_time)
            AuditLogger->>SecurityDB: INSERT INTO audit_logs (async)
            FastAPI-->>User: {"result": "..."}
        end
    else RBAC Disabled
        RBACMiddleware->>FastAPI: Skip RBAC check
        FastAPI->>MCPTool: execute_python(code)
        MCPTool-->>FastAPI: Result
        FastAPI-->>User: {"result": "..."}
    end
```

### 2. Sandbox Execution with Audit Logging

```mermaid
sequenceDiagram
    participant MCPTool
    participant SecureExecutor
    participant SecurityValidator
    participant ContainerSandbox
    participant DockerRuntime
    participant AuditLogger
    participant SecurityDB

    MCPTool->>SecureExecutor: execute_python_code(code, timeout)
    SecureExecutor->>SecurityValidator: validate_code(code)

    alt Validation Failed
        SecurityValidator-->>SecureExecutor: SecurityError
        SecureExecutor->>AuditLogger: log_validation_failure()
        AuditLogger->>SecurityDB: INSERT audit_log (async)
        SecureExecutor-->>MCPTool: Error result
    else Validation Passed
        SecurityValidator-->>SecureExecutor: OK

        SecureExecutor->>ContainerSandbox: run(code, timeout)
        ContainerSandbox->>DockerRuntime: docker run --rm --cap-drop ALL

        alt Execution Success
            DockerRuntime-->>ContainerSandbox: stdout, stderr, returncode=0
            ContainerSandbox->>AuditLogger: log_execution_success()
            AuditLogger->>SecurityDB: INSERT audit_log (async)
            ContainerSandbox-->>SecureExecutor: result
            SecureExecutor-->>MCPTool: Success result
        else Execution Timeout
            DockerRuntime-->>ContainerSandbox: timeout
            ContainerSandbox->>DockerRuntime: docker kill container
            ContainerSandbox->>AuditLogger: log_timeout()
            AuditLogger->>SecurityDB: INSERT audit_log (async)
            ContainerSandbox-->>SecureExecutor: Timeout error
            SecureExecutor-->>MCPTool: Error result
        else Execution Error
            DockerRuntime-->>ContainerSandbox: stderr, returncode!=0
            ContainerSandbox->>AuditLogger: log_execution_error()
            AuditLogger->>SecurityDB: INSERT audit_log (async)
            ContainerSandbox-->>SecureExecutor: Error result
            SecureExecutor-->>MCPTool: Error result
        end
    end
```

### 3. Asynchronous Audit Logging Flow

```mermaid
sequenceDiagram
    participant RBACMiddleware
    participant AuditLogger
    participant AsyncQueue
    participant BackgroundWriter
    participant SecurityDB

    Note over AuditLogger: Initialization
    AuditLogger->>AsyncQueue: Create asyncio.Queue(maxsize=1000)
    AuditLogger->>BackgroundWriter: Start async writer task

    Note over RBACMiddleware: Request Processing
    RBACMiddleware->>AuditLogger: log_tool_call(user_id, tool_name, result)
    AuditLogger->>AuditLogger: Construct log entry dict
    AuditLogger->>AsyncQueue: queue.put(log_entry) [non-blocking]
    AuditLogger-->>RBACMiddleware: Return immediately (<5ms)

    Note over BackgroundWriter: Background Processing
    loop Writer Loop
        BackgroundWriter->>AsyncQueue: await queue.get()
        AsyncQueue-->>BackgroundWriter: log_entry
        BackgroundWriter->>SecurityDB: INSERT INTO audit_logs
        SecurityDB-->>BackgroundWriter: Success

        alt Batch Mode (optional)
            BackgroundWriter->>BackgroundWriter: Accumulate entries
            BackgroundWriter->>SecurityDB: INSERT multiple rows (batch)
        end
    end

    Note over AsyncQueue: Queue Full Handling
    alt Queue Full
        AuditLogger->>AsyncQueue: queue.put(log_entry)
        AsyncQueue-->>AuditLogger: asyncio.QueueFull
        AuditLogger->>AuditLogger: Log warning, drop oldest entry
    end
```

### 4. User Request End-to-End Flow

```mermaid
sequenceDiagram
    participant Client
    participant CORS
    participant RBAC
    participant RateLimit
    participant Tool
    participant Sandbox
    participant Audit
    participant DB

    Client->>CORS: HTTP Request + Headers
    CORS->>CORS: Validate CORS headers
    CORS->>RBAC: Forward request

    RBAC->>RBAC: Extract user_id, tool_name
    RBAC->>DB: Check user permissions
    DB-->>RBAC: permission_granted

    alt Permission Denied
        RBAC->>Audit: Log denial (async)
        RBAC-->>Client: 403 Forbidden
    else Permission Granted
        RBAC->>RateLimit: Forward request

        RateLimit->>RateLimit: Check rate limit
        alt Rate Limit Exceeded
            RateLimit->>Audit: Log rate limit (async)
            RateLimit-->>Client: 429 Too Many Requests
        else Rate Limit OK
            RateLimit->>Tool: Invoke MCP tool

            alt Tool = execute_python
                Tool->>Sandbox: Validate + Execute
                Sandbox->>Sandbox: AST validation
                Sandbox->>Sandbox: Docker container run
                Sandbox->>Audit: Log execution (async)
                Sandbox-->>Tool: Result
            else Tool = read_file
                Tool->>Tool: Safe file API
                Tool->>Audit: Log access (async)
                Tool-->>Tool: File content
            end

            Tool-->>RateLimit: Tool result
            RateLimit-->>RBAC: Tool result
            RBAC-->>CORS: Tool result
            CORS-->>Client: 200 OK + Result
        end
    end

    Note over Audit,DB: Async Logging
    Audit->>DB: INSERT audit_log (background)
```

---

## Component Architecture

### Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│  FastAPI Endpoints, CORS Middleware, HTTP Handlers      │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│                   Security Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ RBAC Middle- │  │ Rate Limiter │  │ Access Ctrl  │  │
│  │    ware      │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│                   Business Logic Layer                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  MCP Tools   │  │ RBAC Manager │  │ Audit Logger │  │
│  │  (18 tools)  │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│                 Execution Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Security   │  │  Container   │  │  Safe File   │  │
│  │  Validator   │  │   Sandbox    │  │     API      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│                   Data Layer                             │
│  ┌────────────────────────┐  ┌───────────────────────┐  │
│  │  Security Database     │  │  Docker Runtime       │  │
│  │  (SQLite WAL Mode)     │  │  (Container Executor) │  │
│  └────────────────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Client Request
    │
    ↓
[CORS Middleware] → Allow origins
    │
    ↓
[RBAC Middleware] → Extract user_id, tool_name
    │               → Check RBAC permission
    │               → If denied: Log + Return 403
    ↓
[Rate Limiter] → Check rate limit
    │          → Check concurrent execution
    │          → If exceeded: Return 429
    ↓
[MCP Tool Handler] → Route to appropriate tool
    │
    ├→ [execute_python]
    │   ├→ SecurityValidator.validate_code()
    │   └→ ContainerSandbox.run()
    │
    ├→ [read_file]
    │   └→ SafeFileAPI.read_text()
    │
    └→ [Other tools]
        └→ Tool-specific logic
    │
    ↓
[Audit Logger] → Queue log entry (async)
    │
    ↓
Response to Client
```

---

## Performance Considerations

### RBAC Permission Cache

**Strategy**: In-memory LRU cache with TTL

```python
cache = {
    "user_id:tool_name": {
        "allowed": True/False,
        "reason": str,
        "cached_at": timestamp,
        "ttl": 300  # 5 minutes
    }
}
```

**Cache Invalidation**:
- On role change: Invalidate all entries for user_id
- On permission change: Invalidate all entries for tool_name
- On TTL expiry: Auto-evict stale entries

### Async Audit Logging

**Queue Size**: 1000 entries (configurable)
**Writer Strategy**: Background task with batch insertion
**Overflow Handling**: Drop oldest entries with warning log

**Performance Targets**:
- Queue insertion: <1ms
- Background write: <10ms per batch
- Total overhead: <5ms (non-blocking)

### Database Optimization

**WAL Mode**: Enable concurrent readers + single writer
**Indexes**:
- user_id (for permission lookups)
- tool_name (for usage statistics)
- timestamp (for log queries)

**Connection Pooling**: Reuse connections across requests

---

## Security Design Principles

1. **Fail Secure**: Default deny for unknown users/permissions
2. **Least Privilege**: Users granted minimum necessary permissions
3. **Defense in Depth**: Multiple security layers (RBAC + Rate Limit + Sandbox)
4. **Audit Everything**: Log all security-relevant events
5. **Feature Flags**: Allow disabling security for testing/debugging
6. **Graceful Degradation**: Continue operation if non-critical components fail

---

## Deployment Architecture

### Development Environment
- RBAC_ENABLED=false
- SANDBOX_ENABLED=true
- RATE_LIMIT_ENABLED=true
- Loose rate limits for testing

### Production Environment
- RBAC_ENABLED=true
- SANDBOX_ENABLED=true
- RATE_LIMIT_ENABLED=true
- Strict rate limits
- Audit log retention: 90 days
- Database backups: Daily
