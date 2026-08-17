"""
Enterprise Intelligence Platform Decorators

Decorators for caching, logging, performance monitoring, and metrics tracking.
"""

import functools
import time
from typing import Any, Callable, Dict, Optional
from datetime import datetime

import frappe


# ============================================================================
# Caching Decorator
# ============================================================================


def cache_result(
    duration: int = 3600,
    key_prefix: str = "eip_cache",
) -> Callable:
    """
    Decorator to cache function results.

    Args:
        duration: Cache duration in seconds (default: 1 hour)
        key_prefix: Prefix for cache key

    Returns:
        Decorated function that caches results
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = cache_key[:200]  # Limit key length

            # Try to get from cache
            try:
                cached = frappe.cache().get_value(cache_key)
                if cached is not None:
                    frappe.logger().debug(f"Cache hit: {cache_key}")
                    return cached
            except Exception as e:
                frappe.logger().warning(f"Cache retrieval failed: {e}")

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            try:
                frappe.cache().set_value(cache_key, result, expires_in_sec=duration)
            except Exception as e:
                frappe.logger().warning(f"Cache storage failed: {e}")

            return result

        return wrapper

    return decorator


# ============================================================================
# Performance Monitoring Decorator
# ============================================================================


def log_performance(
    log_level: str = "info",
    threshold_ms: Optional[int] = None,
) -> Callable:
    """
    Decorator to log function execution time.

    Args:
        log_level: Logging level (debug, info, warning, error)
        threshold_ms: Alert if execution > threshold (milliseconds)

    Returns:
        Decorated function with performance logging
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            start_datetime = datetime.now()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration_seconds = end_time - start_time
                duration_ms = duration_seconds * 1000

                logger = frappe.logger()
                log_message = (
                    f"{func.__name__} executed in {duration_ms:.2f}ms "
                    f"(started at {start_datetime.isoformat()})"
                )

                if threshold_ms and duration_ms > threshold_ms:
                    logger.warning(
                        f"SLOW EXECUTION: {log_message} "
                        f"(threshold: {threshold_ms}ms)"
                    )
                else:
                    getattr(logger, log_level)(log_message)

        return wrapper

    return decorator


# ============================================================================
# Metrics Tracking Decorator
# ============================================================================


def track_metrics(
    metric_prefix: str = "eip",
    track_args: bool = False,
) -> Callable:
    """
    Decorator to track function call metrics.

    Args:
        metric_prefix: Prefix for metric names
        track_args: Whether to log arguments

    Returns:
        Decorated function with metrics tracking
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            metric_key = f"{metric_prefix}:{func.__name__}"

            # Get current metrics
            try:
                metrics = frappe.cache().get_value(f"{metric_key}:metrics") or {
                    "call_count": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "total_duration_ms": 0,
                    "last_called": None,
                }
            except Exception:
                metrics = {
                    "call_count": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "total_duration_ms": 0,
                    "last_called": None,
                }

            # Increment call count
            metrics["call_count"] += 1
            metrics["last_called"] = datetime.now().isoformat()

            # Track arguments if requested
            if track_args:
                metrics["last_args"] = str(args)[:100]
                metrics["last_kwargs"] = str(kwargs)[:100]

            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                metrics["success_count"] += 1
                return result
            except Exception as e:
                metrics["error_count"] += 1
                metrics["last_error"] = str(e)[:200]
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                metrics["total_duration_ms"] += duration_ms
                metrics["avg_duration_ms"] = (
                    metrics["total_duration_ms"] / metrics["call_count"]
                )

                # Store metrics
                try:
                    frappe.cache().set_value(
                        f"{metric_key}:metrics",
                        metrics,
                        expires_in_sec=86400,  # 24 hours
                    )
                except Exception as e:
                    frappe.logger().warning(f"Failed to store metrics: {e}")

        return wrapper

    return decorator


# ============================================================================
# Error Handling Decorator
# ============================================================================


def handle_errors(
    default_return: Any = None,
    log_traceback: bool = True,
    reraise: bool = False,
) -> Callable:
    """
    Decorator for comprehensive error handling.

    Args:
        default_return: Value to return on error
        log_traceback: Whether to log full traceback
        reraise: Whether to re-raise exception

    Returns:
        Decorated function with error handling
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = frappe.logger()

                if log_traceback:
                    logger.error(
                        f"Error in {func.__name__}",
                        exc_info=True,
                    )
                else:
                    logger.error(f"Error in {func.__name__}: {str(e)}")

                if reraise:
                    raise

                return default_return

        return wrapper

    return decorator


# ============================================================================
# Retry Decorator
# ============================================================================


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1,
    backoff_factor: float = 2,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator to retry function execution on failure.

    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_factor: Multiplier for delay (exponential backoff)
        exceptions: Tuple of exceptions to catch

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay_seconds

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        frappe.logger().warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for "
                            f"{func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        frappe.logger().error(
                            f"All {max_attempts} attempts failed for {func.__name__}"
                        )

            raise last_exception

        return wrapper

    return decorator


# ============================================================================
# Validation Decorator
# ============================================================================


def validate_input(
    required_fields: Optional[Dict[str, type]] = None,
) -> Callable:
    """
    Decorator to validate function input arguments.

    Args:
        required_fields: Dictionary of field_name: expected_type

    Returns:
        Decorated function with input validation
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not required_fields:
                return func(*args, **kwargs)

            # Validate kwargs
            for field_name, expected_type in required_fields.items():
                if field_name in kwargs:
                    value = kwargs[field_name]
                    if not isinstance(value, expected_type):
                        raise TypeError(
                            f"Field '{field_name}' must be {expected_type.__name__}, "
                            f"got {type(value).__name__}"
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator
