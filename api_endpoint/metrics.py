"""
Prometheus metrics collection for the Flask API.
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import time
from flask import request, g

# Create a custom registry
REGISTRY = CollectorRegistry()

# Request counters
request_count = Counter(
    'flask_request_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

# Request latency histogram
request_latency = Histogram(
    'flask_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    registry=REGISTRY,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Request size counter
request_size = Counter(
    'flask_request_size_bytes_total',
    'Total size of HTTP requests in bytes',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Response size counter
response_size = Counter(
    'flask_response_size_bytes_total',
    'Total size of HTTP responses in bytes',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

# Rate limit counter
rate_limit_exceeded = Counter(
    'flask_rate_limit_exceeded_total',
    'Total rate limit exceeded errors',
    ['endpoint'],
    registry=REGISTRY
)

# Error counter
errors = Counter(
    'flask_errors_total',
    'Total errors by type',
    ['error_type'],
    registry=REGISTRY
)

# Database connection counter
db_connections = Gauge(
    'flask_db_connections_active',
    'Active database connections',
    registry=REGISTRY
)

# Active requests gauge
active_requests = Gauge(
    'flask_requests_active',
    'Number of active requests',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'flask_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['breaker_name'],
    registry=REGISTRY
)

circuit_breaker_failures = Gauge(
    'flask_circuit_breaker_failures',
    'Number of failures in circuit breaker',
    ['breaker_name'],
    registry=REGISTRY
)


def record_request_start(endpoint):
    """Record the start of a request."""
    g.start_time = time.time()
    g.endpoint = endpoint or 'unknown'
    active_requests.labels(method=request.method, endpoint=g.endpoint).inc()


def record_request_end(status_code, endpoint=None):
    """Record metrics for completed request."""
    endpoint = endpoint or g.get('endpoint', 'unknown')
    
    # Calculate latency
    if hasattr(g, 'start_time'):
        latency = time.time() - g.start_time
        request_latency.labels(method=request.method, endpoint=endpoint).observe(latency)
    
    # Record request and response sizes
    if request.content_length:
        request_size.labels(method=request.method, endpoint=endpoint).inc(request.content_length)
    
    # Estimate response size (Content-Length header)
    response_length = request.headers.get('Content-Length', 0)
    if response_length:
        response_size.labels(
            method=request.method,
            endpoint=endpoint,
            status=status_code
        ).inc(int(response_length))
    
    # Record request count
    request_count.labels(
        method=request.method,
        endpoint=endpoint,
        status=status_code
    ).inc()
    
    # Decrement active requests
    active_requests.labels(method=request.method, endpoint=endpoint).dec()


def record_error(error_type):
    """Record an error."""
    errors.labels(error_type=error_type).inc()


def record_rate_limit(endpoint):
    """Record a rate limit exceeded event."""
    rate_limit_exceeded.labels(endpoint=endpoint).inc()


def update_circuit_breaker_metrics(breaker_name, state, failures):
    """Update circuit breaker metrics."""
    state_value = 0  # closed
    if state == 'open':
        state_value = 1
    elif state == 'half_open':
        state_value = 2
    
    circuit_breaker_state.labels(breaker_name=breaker_name).set(state_value)
    circuit_breaker_failures.labels(breaker_name=breaker_name).set(failures)
