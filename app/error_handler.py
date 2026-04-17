"""
Edge Crew v3.0 - Error Handling Architecture
Circuit breaker pattern with proper async task lifecycle management
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime, timedelta
import time
from functools import wraps
import traceback

logger = logging.getLogger("edge-crew-v3.error_handler")

class ErrorCategory(Enum):
    """Error classification for appropriate handling strategies"""
    NETWORK = "network"  # External API failures
    DATABASE = "database"  # Database connection issues
    VALIDATION = "validation"  # Input validation failures
    RESOURCE = "resource"  # Memory/CPU exhaustion
    TIMEOUT = "timeout"  # Operation timeouts
    UNKNOWN = "unknown"  # Uncategorized errors

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery

class ErrorContext:
    """Context for error handling decisions"""
    def __init__(self, category: ErrorCategory, retry_count: int = 0, 
                 last_error: Optional[Exception] = None, 
                 context_data: Optional[Dict[str, Any]] = None):
        self.category = category
        self.retry_count = retry_count
        self.last_error = last_error
        self.context_data = context_data or {}
        self.timestamp = datetime.utcnow()

class CircuitBreaker:
    """Circuit breaker for external service calls"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: type = Exception, name: str = "circuit"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit {self.name} entering HALF_OPEN state")
                else:
                    raise Exception(f"Circuit {self.name} is OPEN - failing fast")
            
            try:
                result = await func(*args, **kwargs)
                if self.state == CircuitState.HALF_OPEN:
                    self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
                
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.last_failure_time is None:
            return True
        return (datetime.utcnow() - self.last_failure_time).seconds >= self.recovery_timeout
        
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.info(f"Circuit {self.name} recovered - CLOSED state")
        
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"Circuit {self.name} opened after {self.failure_count} failures")

class AsyncTaskManager:
    """Managed async task execution with resource limits and cleanup"""
    
    def __init__(self, max_concurrent_tasks: int = 10, task_timeout: int = 300):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = task_timeout
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_metrics: Dict[str, Dict] = {}
        
    async def create_managed_task(self, coro: Callable, task_id: str, 
                                 *args, **kwargs) -> asyncio.Task:
        """Create a managed async task with timeout and cleanup"""
        
        async def wrapped_coro():
            try:
                self.task_metrics[task_id] = {
                    'start_time': time.time(),
                    'state': 'running',
                    'exception': None
                }
                
                # Execute with timeout
                result = await asyncio.wait_for(coro(*args, **kwargs), 
                                              timeout=self.task_timeout)
                
                self.task_metrics[task_id]['state'] = 'completed'
                return result
                
            except asyncio.TimeoutError:
                self.task_metrics[task_id]['state'] = 'timeout'
                logger.error(f"Task {task_id} timed out after {self.task_timeout}s")
                raise
                
            except Exception as e:
                self.task_metrics[task_id]['state'] = 'failed'
                self.task_metrics[task_id]['exception'] = str(e)
                logger.error(f"Task {task_id} failed: {e}")
                raise
                
            finally:
                # Cleanup
                self.active_tasks.pop(task_id, None)
                
        async with self.semaphore:
            task = asyncio.create_task(wrapped_coro(), name=task_id)
            self.active_tasks[task_id] = task
            
            # Add cleanup callback
            task.add_done_callback(lambda t: self._cleanup_task(task_id))
            
            return task
    
    def _cleanup_task(self, task_id: str):
        """Cleanup task resources"""
        self.active_tasks.pop(task_id, None)
        metrics = self.task_metrics.get(task_id)
        if metrics:
            metrics['end_time'] = time.time()
            metrics['duration'] = metrics['end_time'] - metrics['start_time']
    
    async def cleanup_all_tasks(self):
        """Cleanup all active tasks gracefully"""
        if not self.active_tasks:
            return
            
        logger.info(f"Cleaning up {len(self.active_tasks)} active tasks")
        
        # Cancel all tasks
        for task_id, task in list(self.active_tasks.items()):
            if not task.done():
                task.cancel()
                
        # Wait for cancellation with timeout
        if self.active_tasks:
            await asyncio.wait(self.active_tasks.values(), timeout=10)
            
        self.active_tasks.clear()
        logger.info("All tasks cleaned up")
    
    def get_task_metrics(self) -> Dict[str, Dict]:
        """Get current task execution metrics"""
        return self.task_metrics.copy()
    
    @property
    def active_task_count(self) -> int:
        """Current number of active tasks"""
        return len(self.active_tasks)

def classify_error(error: Exception) -> ErrorCategory:
    """Classify error for appropriate handling strategy"""
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    # Network-related errors
    if any(keyword in error_msg for keyword in ['connection', 'timeout', 'network', 'http']):
        return ErrorCategory.NETWORK
    
    # Database errors
    if any(keyword in error_msg for keyword in ['database', 'postgres', 'sql', 'constraint']):
        return ErrorCategory.DATABASE
    
    # Validation errors
    if any(keyword in error_msg for keyword in ['validation', 'invalid', 'required', 'schema']):
        return ErrorCategory.VALIDATION
    
    # Resource errors
    if any(keyword in error_msg for keyword in ['memory', 'resource', 'limit', 'exhausted']):
        return ErrorCategory.RESOURCE
    
    # Timeout errors
    if 'timeout' in error_msg or asyncio.TimeoutError in type(error).__mro__:
        return ErrorCategory.TIMEOUT
    
    return ErrorCategory.UNKNOWN

def retry_with_backoff(func: Callable, max_retries: int = 3, 
                      base_delay: float = 1.0, max_delay: float = 60.0,
                      exponential_base: float = 2.0) -> Callable:
    """Decorator for retry logic with exponential backoff"""
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                    raise
                
                # Calculate backoff delay
                delay = min(base_delay * (exponential_base ** (retry_count - 1)), max_delay)
                
                error_category = classify_error(e)
                logger.warning(f"Retry {retry_count}/{max_retries} for {func.__name__} "
                             f"after {error_category.value} error: {e}")
                
                await asyncio.sleep(delay)
        
        return None
    
    return wrapper

# Global task manager instance
task_manager = AsyncTaskManager(max_concurrent_tasks=10, task_timeout=300)

# Circuit breakers for external services
odds_api_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="odds_api")
espn_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="espn")
ai_circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=120, name="ai_models")