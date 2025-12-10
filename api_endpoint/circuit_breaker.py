"""
Circuit breaker implementation for the Flask API.
Prevents cascading failures by stopping requests to failing services.
"""
from pybreaker import CircuitBreaker
from .logger import api_logger
from .metrics import record_error
import functools

# Circuit breakers for different services
db_breaker = CircuitBreaker(
    fail_max=5,  # Open after 5 failures
    reset_timeout=60,  # Try to close after 60 seconds
    listeners=[],  # Can add custom listeners
    name='database'
)

redis_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name='redis'
)

auth_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=45,
    name='authentication'
)

external_api_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name='external_api'
)


def configure_breaker_listeners():
    """Configure circuit breaker event listeners."""
    
    def on_state_change(cb, old_state, new_state):
        """Log circuit breaker state changes and update metrics."""
        api_logger.warning(
            f"Circuit breaker '{cb.name}' state changed: {old_state} -> {new_state}"
        )
        record_error(f"CircuitBreaker_{cb.name}_{new_state}")
        
        # Update Prometheus metrics
        from .metrics import update_circuit_breaker_metrics
        update_circuit_breaker_metrics(cb.name, new_state, cb.fail_counter)
    
    # Add listeners to all breakers
    for breaker in [db_breaker, redis_breaker, auth_breaker, external_api_breaker]:
        breaker.listeners = [on_state_change]


def circuit_breaker_check(breaker_name='db'):
    """Decorator to wrap functions with circuit breaker logic."""
    breaker_map = {
        'db': db_breaker,
        'redis': redis_breaker,
        'auth': auth_breaker,
        'external_api': external_api_breaker
    }
    
    selected_breaker = breaker_map.get(breaker_name, db_breaker)
    
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return selected_breaker.call(f, *args, **kwargs)
            except Exception as e:
                api_logger.error(
                    f"Circuit breaker '{selected_breaker.name}' is {selected_breaker.state}: {str(e)}"
                )
                raise
        return wrapper
    return decorator


def get_breaker_status():
    """Get status of all circuit breakers."""
    return {
        'database': {
            'state': db_breaker.state,
            'fail_counter': db_breaker.fail_counter
        },
        'redis': {
            'state': redis_breaker.state,
            'fail_counter': redis_breaker.fail_counter
        },
        'authentication': {
            'state': auth_breaker.state,
            'fail_counter': auth_breaker.fail_counter
        },
        'external_api': {
            'state': external_api_breaker.state,
            'fail_counter': external_api_breaker.fail_counter
        }
    }
