# main.py Migration Guide

## ⚠️ DEPRECATION NOTICE

**`main.py` is deprecated and will be removed in a future version.**

Please migrate to `openapi_server.py` as the primary server implementation. All components have been moved to the `lib/` package for better organization and maintainability.

## Migration Path

### 1. Server Execution

**Before (Deprecated):**
```bash
python main.py
```

**After (Recommended):**
```bash
python openapi_server.py
# or
npm run dev
# or
./scripts/dev.sh
```

### 2. Component Imports

**Before (Deprecated):**
```python
from main import Settings, IntelligentCache, ErrorHandler
from main import BMCAMIDevXClient, HealthChecker, RateLimiter
from main import HybridMetrics, get_metrics, initialize_metrics
```

**After (Recommended):**
```python
from lib import Settings, IntelligentCache, ErrorHandler
from lib import BMCAMIDevXClient, HealthChecker, RateLimiter
from lib import HybridMetrics, get_metrics, initialize_metrics
```

### 3. Tool Usage

**Before (Deprecated):**
```python
# Tools were defined in main.py
from main import some_tool
```

**After (Recommended):**
```python
# Tools are auto-generated from OpenAPI spec in openapi_server.py
from openapi_server import some_tool
```

### 4. Configuration

**Before (Deprecated):**
```python
# Configuration was mixed in main.py
from main import settings
```

**After (Recommended):**
```python
# Configuration is in dedicated lib module
from lib.settings import Settings
settings = Settings()
```

## Key Differences

| Aspect | main.py (Deprecated) | openapi_server.py (Current) |
|--------|---------------------|----------------------------|
| **Architecture** | Monolithic | Component Library + Server |
| **Components** | Embedded in main file | Organized in `lib/` package |
| **Tools** | Manually defined | Auto-generated from OpenAPI |
| **Testing** | Limited coverage | Comprehensive test suite |
| **Maintainability** | Difficult to maintain | Modular and testable |
| **Performance** | Basic implementation | Optimized with advanced features |

## Component Library Architecture

The new architecture separates concerns into dedicated modules:

```
lib/
├── __init__.py          # Main exports
├── settings.py          # Configuration management
├── clients.py           # BMC API client
├── cache.py            # Intelligent caching
├── auth.py             # Authentication & rate limiting
├── health.py           # Health checking
├── errors.py           # Error handling & retry logic
└── metrics.py          # Metrics collection (via observability/)
```

## Advanced Features

The new `openapi_server.py` includes advanced features not available in `main.py`:

- **Hybrid Implementation**: Uses advanced `lib/` components when available, falls back to simple implementations
- **OpenTelemetry Integration**: Comprehensive observability with metrics, tracing, and logging
- **Enhanced Error Handling**: Sophisticated retry logic and error categorization
- **Intelligent Caching**: LRU/TTL cache with cleanup and statistics
- **Rate Limiting**: Token bucket algorithm with burst capacity
- **Health Monitoring**: Comprehensive health checks and status reporting

## Migration Timeline

| Phase | Status | Action Required |
|-------|--------|----------------|
| **Phase 1** | ✅ Complete | Component library created in `lib/` |
| **Phase 2** | ✅ Complete | `openapi_server.py` enhanced with hybrid implementation |
| **Phase 3** | ✅ Complete | `main.py` marked as deprecated with warnings |
| **Phase 4** | 🔄 Current | Remove `main.py` from coverage targets |
| **Phase 5** | 📅 Future | Remove `main.py` entirely |

## Testing Changes

**Before (Deprecated):**
```bash
# Tests included main.py coverage
pytest --cov=main
```

**After (Current):**
```bash
# Tests focus on openapi_server.py and lib/ components
pytest --cov=openapi_server --cov=lib
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Update imports from `main` to `lib` modules
2. **Tool Not Found**: Tools are now in `openapi_server.py`
3. **Configuration Issues**: Use `lib.settings.Settings()` instead of `main.settings`

### Getting Help

- Check the [Architecture Documentation](architecture.md)
- Review [API Reference](api-reference.md)
- See [Component Library Tests](../tests/test_lib_*.py) for usage examples

## Benefits of Migration

✅ **Better Organization**: Components are logically separated and easier to find
✅ **Improved Testing**: Each component has comprehensive test coverage
✅ **Enhanced Performance**: Advanced implementations with optimizations
✅ **Better Maintainability**: Modular architecture is easier to maintain and extend
✅ **Future-Proof**: Component library architecture supports future enhancements
✅ **Production Ready**: Comprehensive error handling, monitoring, and observability

## Questions?

If you have questions about the migration, please:

1. Check this migration guide
2. Review the [Architecture Documentation](architecture.md)
3. Look at the test files for usage examples
4. Check the component library source code in `lib/`

The migration is designed to be straightforward with clear benefits for maintainability, testability, and performance.
