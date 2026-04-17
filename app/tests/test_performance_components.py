"""
Tests for performance foundation components
"""

import os
import asyncio
import pytest

os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from app.error_handler import (
    task_manager,
    CircuitBreaker,
    ErrorCategory,
    classify_error,
    retry_with_backoff,
)
from app.cache import CacheConfig, RedisCache, cache_key_generator
from app.database import DatabaseConfig, DatabaseManager


class TestCircuitBreaker:
    """Test circuit breaker pattern"""

    @pytest.mark.asyncio
    async def test_circuit_starts_closed(self):
        circuit = CircuitBreaker(name="test")
        assert circuit.state.value == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        circuit = CircuitBreaker(failure_threshold=2, name="test")
        
        async def failing_func():
            raise Exception("fail")
        
        # First failure
        with pytest.raises(Exception):
            await circuit.call(failing_func)
        assert circuit.state.value == "closed"
        
        # Second failure - circuit should open
        with pytest.raises(Exception):
            await circuit.call(failing_func)
        assert circuit.state.value == "open"
        
        # Third call should fail fast
        with pytest.raises(Exception) as exc_info:
            await circuit.call(failing_func)
        assert "OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_circuit_closes_on_success(self):
        circuit = CircuitBreaker(failure_threshold=1, recovery_timeout=0, name="test")
        
        async def success_func():
            return "success"
        
        result = await circuit.call(success_func)
        assert result == "success"
        assert circuit.state.value == "closed"


class TestTaskManager:
    """Test async task management"""

    @pytest.mark.asyncio
    async def test_create_managed_task(self):
        async def sample_task():
            await asyncio.sleep(0.01)
            return "done"
        
        task = await task_manager.create_managed_task(sample_task, "test-task-1")
        result = await task
        assert result == "done"
    
    @pytest.mark.asyncio
    async def test_task_metrics_tracked(self):
        async def sample_task():
            return "done"
        
        task_id = "test-task-metrics"
        task = await task_manager.create_managed_task(sample_task, task_id)
        await task
        
        metrics = task_manager.get_task_metrics()
        assert task_id in metrics
        assert metrics[task_id]["state"] == "completed"
    
    @pytest.mark.asyncio
    async def test_cleanup_all_tasks(self):
        async def slow_task():
            await asyncio.sleep(10)
        
        task = await task_manager.create_managed_task(slow_task, "slow-task")
        assert task_manager.active_task_count >= 1
        
        await task_manager.cleanup_all_tasks()
        assert task_manager.active_task_count == 0


class TestErrorClassification:
    """Test error classification"""

    def test_network_error_classification(self):
        error = Exception("Connection timeout to api.example.com")
        category = classify_error(error)
        assert category == ErrorCategory.NETWORK
    
    def test_database_error_classification(self):
        error = Exception("postgres constraint violation")
        category = classify_error(error)
        assert category == ErrorCategory.DATABASE
    
    def test_validation_error_classification(self):
        error = Exception("validation failed: invalid schema")
        category = classify_error(error)
        assert category == ErrorCategory.VALIDATION
    
    def test_timeout_error_classification(self):
        error = asyncio.TimeoutError("Operation timed out")
        category = classify_error(error)
        assert category == ErrorCategory.TIMEOUT


class TestRetryWithBackoff:
    """Test retry decorator"""

    @pytest.mark.asyncio
    async def test_retry_succeeds_eventually(self):
        call_count = 0
        
        async def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("temporary failure")
            return "success"
        
        decorated = retry_with_backoff(sometimes_fails, max_retries=3, base_delay=0.01)
        result = await decorated()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausts_max_retries(self):
        async def always_fails():
            raise Exception("persistent failure")
        
        with pytest.raises(Exception):
            await retry_with_backoff(always_fails, max_retries=2, base_delay=0.01)


class TestCacheConfig:
    """Test cache configuration"""

    def test_default_config(self):
        config = CacheConfig()
        assert config.redis_url == "redis://redis:6379"
        assert config.default_ttl == 3600
        assert config.validate_config() is True
    
    def test_cache_key_generator(self):
        key = cache_key_generator("test", "arg1", "arg2", param1="value1")
        assert key == "test:arg1:arg2:param1:value1"


class TestDatabaseConfig:
    """Test database configuration"""

    def test_default_config(self):
        config = DatabaseConfig()
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30
        assert config.validate_config() is True
    
    def test_database_manager_creation(self):
        config = DatabaseConfig()
        manager = DatabaseManager(config)
        assert manager.config == config
        assert manager.engine is None


class TestSchedulerConfig:
    """Test scheduler configuration externalization"""

    def test_default_scheduler_config(self):
        import importlib
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "data-ingestion"))
        scheduler_module = importlib.import_module("services.data-ingestion.scheduler")
        SchedulerConfig = getattr(scheduler_module, "SchedulerConfig")
        
        config = SchedulerConfig()
        assert config.critical_threshold == 15
        assert config.high_threshold == 8
        from models import Priority
        assert config.fetch_intervals[Priority.CRITICAL] == 30
        assert config.fetch_intervals[Priority.HIGH] == 120
        assert config.dedup_window == 60
        assert config.max_age_hours == 48
    
    def test_custom_scheduler_config_from_env(self, monkeypatch):
        import importlib
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "data-ingestion"))
        scheduler_module = importlib.import_module("services.data-ingestion.scheduler")
        SchedulerConfig = getattr(scheduler_module, "SchedulerConfig")
        
        monkeypatch.setenv("SCHEDULER_CRITICAL_THRESHOLD", "20")
        monkeypatch.setenv("SCHEDULER_HIGH_THRESHOLD", "10")
        monkeypatch.setenv("SCHEDULER_CRITICAL_INTERVAL", "60")
        
        config = SchedulerConfig()
        assert config.critical_threshold == 20
        assert config.high_threshold == 10
        from models import Priority
        assert config.fetch_intervals[Priority.CRITICAL] == 60