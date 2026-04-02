"""Synthetic incident scenarios for each task difficulty."""

SCENARIOS = {
    "task_easy": {
        "title": "Single Service Outage",
        "description": (
            "The payment-service is returning 500 errors. "
            "Identify the root cause and apply the correct fix."
        ),
        "alerts": [
            "[CRITICAL] payment-service: HTTP 500 error rate > 80%",
            "[WARNING] payment-service: response latency p99 = 12s",
        ],
        "logs": {
            "payment-service": [
                "ERROR: Connection refused to postgres-db:5432",
                "ERROR: Connection refused to postgres-db:5432",
                "ERROR: Failed to process payment for order #8821",
                "ERROR: Connection refused to postgres-db:5432",
            ],
            "postgres-db": [
                "FATAL: max_connections limit reached (100/100)",
                "FATAL: max_connections limit reached (100/100)",
            ],
            "api-gateway": [
                "WARN: Upstream payment-service returning 500",
            ],
        },
        "metrics": {
            "payment-service": {"error_rate": 0.85, "latency_p99_ms": 12000, "rps": 42},
            "postgres-db": {"connections": 100, "max_connections": 100, "cpu": 0.3},
        },
        "root_cause": "postgres-db",
        "correct_fix": "increase_db_connections",
        "correct_escalation": "database-team",
        "available_services": ["payment-service", "postgres-db", "api-gateway", "auth-service"],
        "available_fixes": ["increase_db_connections", "restart_payment_service", "rollback_deployment", "scale_up_pods"],
        "available_teams": ["database-team", "backend-team", "infra-team", "security-team"],
    },

    "task_medium": {
        "title": "Cascading Microservice Failure",
        "description": (
            "Multiple services are degraded. The checkout flow is broken. "
            "Identify which service is the origin of the cascade, escalate to the right team, "
            "apply the fix, and submit a postmortem."
        ),
        "alerts": [
            "[CRITICAL] checkout-service: HTTP 503 error rate > 90%",
            "[CRITICAL] inventory-service: HTTP 500 error rate > 60%",
            "[WARNING] notification-service: message queue depth > 50000",
            "[WARNING] api-gateway: upstream errors on /checkout endpoint",
        ],
        "logs": {
            "checkout-service": [
                "ERROR: inventory-service returned 500 for stock check",
                "ERROR: inventory-service returned 500 for stock check",
                "ERROR: Failed to complete checkout for user #4421",
            ],
            "inventory-service": [
                "ERROR: redis-cache connection timeout after 30s",
                "ERROR: redis-cache connection timeout after 30s",
                "ERROR: Falling back to postgres-db — latency high",
                "ERROR: postgres-db query timeout after 30s",
            ],
            "redis-cache": [
                "WARN: Memory usage at 99% (3.96GB / 4GB)",
                "ERROR: OOM — evicting keys",
                "ERROR: OOM — evicting keys",
            ],
            "notification-service": [
                "WARN: Queue consumer lag increasing",
                "WARN: Failed to send order confirmation — checkout errors upstream",
            ],
            "api-gateway": [
                "ERROR: /checkout upstream timeout",
            ],
        },
        "metrics": {
            "checkout-service": {"error_rate": 0.92, "latency_p99_ms": 30000},
            "inventory-service": {"error_rate": 0.63, "latency_p99_ms": 31000},
            "redis-cache": {"memory_used_gb": 3.96, "memory_max_gb": 4.0, "evictions_per_sec": 850},
            "notification-service": {"queue_depth": 52000},
        },
        "root_cause": "redis-cache",
        "correct_fix": "flush_redis_cache",
        "correct_escalation": "infra-team",
        "available_services": ["checkout-service", "inventory-service", "redis-cache", "notification-service", "api-gateway", "postgres-db"],
        "available_fixes": ["flush_redis_cache", "restart_checkout_service", "scale_up_redis", "rollback_deployment", "increase_db_connections"],
        "available_teams": ["infra-team", "backend-team", "database-team", "frontend-team", "security-team"],
        "postmortem_keywords": ["redis", "memory", "oom", "cache", "eviction"],
    },

    "task_hard": {
        "title": "Intermittent Auth Failure with Data Corruption Risk",
        "description": (
            "Users are intermittently failing to authenticate. Some sessions show corrupted data. "
            "The issue is non-deterministic. Investigate all services, identify the root cause "
            "(a misconfigured JWT secret rotation), escalate to the right team, apply the correct fix, "
            "and write a detailed postmortem covering impact, root cause, and prevention."
        ),
        "alerts": [
            "[CRITICAL] auth-service: 401 error rate spiking intermittently (30-70%)",
            "[WARNING] user-service: data inconsistency detected in session store",
            "[WARNING] audit-log: unusual token validation failures from multiple regions",
            "[INFO] config-service: secret rotation job ran 2 hours ago",
        ],
        "logs": {
            "auth-service": [
                "ERROR: JWT signature verification failed for token issued 1h ago",
                "INFO: JWT signature verification succeeded for token issued 30m ago",
                "ERROR: JWT signature verification failed for token issued 1.5h ago",
                "WARN: Multiple JWT secrets active — rotation in progress?",
                "ERROR: JWT signature verification failed for token issued 2h ago",
            ],
            "config-service": [
                "INFO: Secret rotation job started at 14:00 UTC",
                "INFO: New JWT secret deployed to auth-service replica 1/3",
                "INFO: New JWT secret deployed to auth-service replica 2/3",
                "ERROR: Failed to deploy new JWT secret to auth-service replica 3/3 — timeout",
                "INFO: Secret rotation job marked complete (partial)",
            ],
            "user-service": [
                "WARN: Session data mismatch for user #9921 — possible stale token",
                "WARN: Session data mismatch for user #1043",
                "ERROR: Cannot deserialize session — token claims invalid",
            ],
            "audit-log": [
                "WARN: 847 token validation failures in last 60 minutes",
                "WARN: Failures distributed across all regions — not a network issue",
            ],
        },
        "metrics": {
            "auth-service": {"error_rate_intermittent": 0.45, "replicas_with_new_secret": 2, "total_replicas": 3},
            "config-service": {"last_rotation_success_rate": 0.67},
            "user-service": {"session_inconsistency_rate": 0.31},
        },
        "root_cause": "config-service",
        "correct_fix": "complete_secret_rotation",
        "correct_escalation": "security-team",
        "available_services": ["auth-service", "config-service", "user-service", "audit-log", "api-gateway", "redis-cache"],
        "available_fixes": ["complete_secret_rotation", "rollback_jwt_secret", "restart_auth_service", "flush_redis_cache", "scale_up_auth_replicas"],
        "available_teams": ["security-team", "backend-team", "infra-team", "database-team", "frontend-team"],
        "postmortem_keywords": ["jwt", "secret", "rotation", "config", "replica", "partial", "auth"],
    },
}
