#!/usr/bin/env python3
"""
Tests for Circuit Breaker functionality.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock

from lib.errors import CircuitBreaker, CircuitBreakerOpenError, CircuitBreakerState


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.last_failure_time is None

    def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def success_func():
            return "success"
            
        result = cb.call(success_func)
        assert result == "success"
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_func():
            raise Exception("Test failure")
            
        # First failure
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_open_state(self):
        """Test circuit breaker rejects calls when open."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise Exception("Test failure")
            
        # Trigger failure to open circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Next call should be rejected
        def success_func():
            return "success"
            
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(success_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_success(self):
        """Test circuit breaker with async successful calls."""
        cb = CircuitBreaker(failure_threshold=3)
        
        async def async_success_func():
            return "async_success"
            
        result = await cb.acall(async_success_func)
        assert result == "async_success"
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_failure(self):
        """Test circuit breaker with async failing calls."""
        cb = CircuitBreaker(failure_threshold=1)
        
        async def async_failing_func():
            raise Exception("Async test failure")
            
        # Trigger failure to open circuit
        with pytest.raises(Exception):
            await cb.acall(async_failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Next call should be rejected
        async def async_success_func():
            return "async_success"
            
        with pytest.raises(CircuitBreakerOpenError):
            await cb.acall(async_success_func)

    def test_circuit_breaker_recovery_after_timeout(self):
        """Test circuit breaker recovery after timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        def failing_func():
            raise Exception("Test failure")
            
        # Trigger failure to open circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Next call should transition to half-open
        def success_func():
            return "success"
            
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_half_open_success(self):
        """Test circuit breaker half-open state with success."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        # Open the circuit
        def failing_func():
            raise Exception("Test failure")
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Success should close the circuit
        def success_func():
            return "success"
        result = cb.call(success_func)
        
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker half-open state with failure."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        # Open the circuit
        def failing_func():
            raise Exception("Test failure")
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Failure should re-open the circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 2
