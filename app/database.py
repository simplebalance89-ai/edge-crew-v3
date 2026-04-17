"""
Edge Crew v3.0 - Database Connection Management
SQLAlchemy connection pooling with Render PostgreSQL optimization
"""

import os
import logging
from typing import Optional, Generator, Any
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import time

logger = logging.getLogger("edge-crew-v3.database")

class DatabaseConfig:
    """Database configuration with Render-optimized settings"""
    
    def __init__(self):
        # Render PostgreSQL connection limits (Standard tier)
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
        
        # Connection string
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            # Use a default SQLite URL for testing/development without PostgreSQL
            self.database_url = "sqlite:///./test.db"
            logger.warning("DATABASE_URL not set, using SQLite for testing")
            
        # TimescaleDB optimization
        self.chunk_time_interval = os.getenv("DB_CHUNK_INTERVAL", "1 day")
        self.enable_compression = os.getenv("DB_ENABLE_COMPRESSION", "true").lower() == "true"
        
    def validate_config(self) -> bool:
        """Validate database configuration"""
        try:
            # Test connection parameters
            assert self.pool_size > 0, "Pool size must be positive"
            assert self.max_overflow >= 0, "Max overflow must be non-negative"
            assert self.pool_timeout > 0, "Pool timeout must be positive"
            assert self.pool_recycle > 0, "Pool recycle must be positive"
            
            # Render Standard tier limits
            total_connections = self.pool_size + self.max_overflow
            if total_connections > 25:  # Render PostgreSQL limit
                logger.warning(f"Total connections ({total_connections}) exceeds Render limit (25)")
                
            return True
        except Exception as e:
            logger.error(f"Database configuration validation failed: {e}")
            return False

class DatabaseManager:
    """Database connection manager with pooling and monitoring"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.connection_metrics = {
            'active_connections': 0,
            'total_connections': 0,
            'checkouts': 0,
            'checkins': 0,
            'errors': 0
        }
        
    def create_engine_with_pooling(self) -> Engine:
        """Create SQLAlchemy engine with optimized connection pooling"""
        
        # Connection pool configuration for Render PostgreSQL
        engine = create_engine(
            self.config.database_url,
            poolclass=QueuePool,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )
        
        # Add connection event listeners for monitoring
        self._setup_connection_events(engine)
        
        return engine
    
    def _setup_connection_events(self, engine: Engine):
        """Setup connection event listeners for monitoring"""
        
        @event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            self.connection_metrics['total_connections'] += 1
            self.connection_metrics['active_connections'] += 1
            logger.debug(f"Database connection established. Active: {self.connection_metrics['active_connections']}")
        
        @event.listens_for(engine, "close")
        def close(dbapi_connection, connection_record):
            self.connection_metrics['active_connections'] -= 1
            logger.debug(f"Database connection closed. Active: {self.connection_metrics['active_connections']}")
        
        @event.listens_for(engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            self.connection_metrics['checkouts'] += 1
            logger.debug(f"Connection checked out. Total checkouts: {self.connection_metrics['checkouts']}")
        
        @event.listens_for(engine, "checkin")
        def checkin(dbapi_connection, connection_record):
            self.connection_metrics['checkins'] += 1
            logger.debug(f"Connection checked in. Total checkins: {self.connection_metrics['checkins']}")
        
        @event.listens_for(engine, "error")
        def error_event(exception_context):
            self.connection_metrics['errors'] += 1
            logger.error(f"Database connection error: {exception_context.original_exception}")
    
    def initialize(self):
        """Initialize database engine and session factory"""
        try:
            if not self.config.validate_config():
                raise ValueError("Invalid database configuration")
                
            self.engine = self.create_engine_with_pooling()
            self.session_factory = sessionmaker(bind=self.engine)
            
            logger.info(f"Database manager initialized with pooling: "
                       f"pool_size={self.config.pool_size}, "
                       f"max_overflow={self.config.max_overflow}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with automatic cleanup"""
        if not self.session_factory:
            raise RuntimeError("Database manager not initialized")
            
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_connection_metrics(self) -> dict:
        """Get current connection pool metrics"""
        return {
            **self.connection_metrics,
            'pool_size': self.config.pool_size,
            'max_overflow': self.config.max_overflow,
            'pool_timeout': self.config.pool_timeout,
            'pool_pre_ping': self.config.pool_pre_ping
        }
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            with self.get_session() as session:
                # Simple query to test connection
                result = session.execute("SELECT 1").scalar()
                return result == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def optimize_for_timescale(self):
        """Apply TimescaleDB-specific optimizations"""
        try:
            with self.get_session() as session:
                # Enable TimescaleDB extensions
                session.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
                
                # Set compression policies if enabled
                if self.config.enable_compression:
                    # Add compression policies for time-series tables
                    compression_queries = [
                        """SELECT add_compression_policy('odds_history', INTERVAL '7 days') 
                           IF NOT EXISTS (SELECT 1 FROM timescaledb_information.policies 
                           WHERE hypertable_name = 'odds_history' AND policy_name = 'compression_policy');""",
                        
                        """SELECT add_compression_policy('grades', INTERVAL '7 days') 
                           IF NOT EXISTS (SELECT 1 FROM timescaledb_information.policies 
                           WHERE hypertable_name = 'grades' AND policy_name = 'compression_policy');""",
                        
                        """SELECT add_compression_policy('model_performance', INTERVAL '30 days') 
                           IF NOT EXISTS (SELECT 1 FROM timescaledb_information.policies 
                           WHERE hypertable_name = 'model_performance' AND policy_name = 'compression_policy');"""
                    ]
                    
                    for query in compression_queries:
                        try:
                            session.execute(query)
                        except Exception as e:
                            logger.warning(f"Compression policy setup failed: {e}")
                
                session.commit()
                logger.info("TimescaleDB optimization completed")
                
        except Exception as e:
            logger.error(f"TimescaleDB optimization failed: {e}")
            raise

# Global database manager instance
_db_config = DatabaseConfig()
_db_manager = DatabaseManager(_db_config)

def initialize_database():
    """Initialize global database manager"""
    _db_manager.initialize()
    return _db_manager

def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    if not _db_manager.engine:
        raise RuntimeError("Database manager not initialized. Call initialize_database() first.")
    return _db_manager

def get_db_session():
    """Get database session context manager"""
    return _db_manager.get_session()