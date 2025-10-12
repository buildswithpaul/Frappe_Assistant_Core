# Performance Guide

Comprehensive guide to monitoring, optimizing, and scaling Frappe Assistant Core for production environments.

## 📊 Performance Metrics

### System Benchmarks (v2.0.0)

#### Core Improvements

- **30% faster tool execution** through optimized plugin loading
- **25% reduced memory footprint** with better resource management  
- **Enhanced error recovery** with graceful failure handling
- **50% faster repeated operations** with improved caching system

#### Scalability Enhancements

- **Plugin lazy loading** reduces startup time
- **Concurrent tool execution** support
- **Better database query optimization** 
- **Enhanced connection pooling**

### Response Time Targets

| Operation Type | Target Response Time | Acceptable Range |
|----------------|---------------------|------------------|
| Document Read | < 100ms | 100-300ms |
| Document Create | < 200ms | 200-500ms |
| Simple Search | < 200ms | 200-600ms |
| Report Execution | < 1s | 1-5s |
| Python Code Execution | < 2s | 2-10s |
| Chart Generation | < 500ms | 500ms-2s |

## 🔧 Performance Monitoring

### Built-in Monitoring

#### Audit Trail Performance

All operations are logged with timing information:

```python
# Check recent performance
from frappe_assistant_core.utils.audit_trail import get_audit_summary

# Get performance data for last 7 days
summary = get_audit_summary(days=7)
print(f"Total operations: {summary['total_events']}")
print(f"Average response time: {summary.get('avg_response_time', 'N/A')}")
```

#### System Health Check

```python
# Enable debug logging
from frappe_assistant_core.utils.logger import api_logger
api_logger.setLevel('DEBUG')

# Check system health
from frappe_assistant_core.core.tool_registry import ToolRegistry
registry = ToolRegistry()
tools = registry.get_all_tools()
print(f"Available tools: {len(tools)}")

# Check plugin status
from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
pm = get_plugin_manager()
plugins = pm.get_enabled_plugins()
print(f"Enabled plugins: {[p.name for p in plugins]}")
```

### External Monitoring

#### Database Performance

Monitor key metrics:

```sql
-- Check slow queries
SELECT * FROM information_schema.processlist 
WHERE time > 5 AND command != 'Sleep';

-- Monitor Assistant table sizes
SELECT 
    table_name,
    table_rows,
    data_length,
    index_length
FROM information_schema.tables 
WHERE table_name LIKE '%assistant%';

-- Check recent audit log performance
SELECT 
    action,
    COUNT(*) as count,
    AVG(execution_time) as avg_time,
    MAX(execution_time) as max_time
FROM `tabAssistant Audit Log`
WHERE creation >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
GROUP BY action
ORDER BY avg_time DESC;
```

#### System Resources

Monitor these key resources:

- **CPU Usage**: Should stay below 70% during normal operations
- **Memory Usage**: Python processes typically use 100-500MB each
- **Database Connections**: Monitor active connections to prevent exhaustion  
- **Disk I/O**: Watch for excessive read/write operations

## ⚡ Optimization Strategies

### 1. Plugin Configuration

#### Selective Plugin Loading

Only enable plugins you actually use:

```python
# Via Admin Interface
https://yoursite.com/desk#/assistant-admin

# Or via code
from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
pm = get_plugin_manager()

# Disable unused plugins
pm.disable_plugin('data_science')  # If not doing analysis
pm.disable_plugin('visualization') # If not creating charts
```

#### Plugin-Specific Optimizations

```python
# In hooks.py - Configure tool-specific limits
assistant_tool_configs = {
    "list_documents": {
        "max_records": 1000,  # Limit large queries
        "timeout": 30         # Prevent long-running queries
    },
    "execute_python_code": {
        "timeout": 60,        # Allow more time for analysis
        "memory_limit": "512MB"
    }
}
```

### 2. Database Optimization

#### Index Management

Ensure proper indexes exist:

```sql
-- Add indexes for common queries
CREATE INDEX idx_audit_log_timestamp ON `tabAssistant Audit Log` (timestamp);
CREATE INDEX idx_audit_log_user_action ON `tabAssistant Audit Log` (user, action);

-- Check index usage
SHOW INDEX FROM `tabAssistant Audit Log`;
```

#### Query Optimization

```python
# Use efficient filtering
good_filter = {
    "doctype": "Sales Invoice",
    "status": "Paid",
    "posting_date": [">", "2024-01-01"]
}

# Avoid open-ended queries
bad_filter = {}  # This will scan entire table
```

### 3. Caching Strategies

#### Built-in Caching

The system includes several caching layers:

```python
# Cache configuration in site_config.json
{
    "redis_cache": "redis://localhost:6379/1",
    "cache_timeout": 3600,
    "background_workers": 4
}
```

#### Custom Caching

For frequently accessed data:

```python
import frappe
from frappe.utils import cint

@frappe.cache(ttl=3600)  # Cache for 1 hour
def get_customer_summary():
    return frappe.db.sql("""
        SELECT customer_group, COUNT(*) as count
        FROM `tabCustomer` 
        GROUP BY customer_group
    """, as_dict=True)
```

### 4. Memory Management

#### Python Process Management

```bash
# Monitor memory usage
ps aux | grep frappe | grep -v grep

# Restart workers periodically
bench restart
```

#### Large Dataset Handling

```python
# For large datasets, use chunking
def process_large_dataset(doctype, filters=None):
    chunk_size = 1000
    start = 0
    
    while True:
        records = frappe.get_all(
            doctype,
            filters=filters,
            limit_start=start,
            limit_page_length=chunk_size
        )
        
        if not records:
            break
            
        # Process chunk
        yield from records
        start += chunk_size
```

## 🎯 Production Deployment

### Server Sizing Recommendations

#### Small Deployment (< 100 users, < 10K documents)

- **CPU**: 2-4 cores
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: SSD recommended, 100GB+
- **Network**: Standard broadband

#### Medium Deployment (100-500 users, 10K-100K documents)

- **CPU**: 4-8 cores  
- **RAM**: 16GB minimum, 32GB recommended
- **Storage**: SSD required, 500GB+
- **Network**: High-speed connection
- **Additional**: Consider read replicas

#### Large Deployment (500+ users, 100K+ documents)

- **CPU**: 8+ cores across multiple servers
- **RAM**: 32GB+ per server
- **Storage**: SSD required, 1TB+
- **Network**: Dedicated high-speed
- **Additional**: Load balancers, multiple app servers

### Configuration Optimization

#### Production Settings

```python
# site_config.json optimizations
{
    "db_timeout": 30,
    "socketio_workers": 4,
    "background_workers": 6,
    "async_redis": true,
    "redis_cache": "redis://localhost:6379/1",
    "redis_queue": "redis://localhost:6379/2",
    "redis_socketio": "redis://localhost:6379/3"
}
```

#### Frappe Configuration

```bash
# In common_site_config.json
{
    "maintenance_mode": 0,
    "pause_scheduler": 0,
    "developer_mode": 0,
    "disable_logging": 0,
    "log_level": "INFO"
}
```

### Load Balancing

#### Multiple App Servers

```nginx
# Nginx configuration example
upstream frappe_servers {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    location / {
        proxy_pass http://frappe_servers;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
    }
}
```

## 📈 Scaling Considerations

### Horizontal Scaling

#### Database Scaling

- **Read Replicas**: For read-heavy workloads
- **Sharding**: For very large datasets
- **Connection Pooling**: Prevent connection exhaustion

#### Application Scaling

- **Multiple App Servers**: Distribute load across servers  
- **Background Workers**: Scale worker processes based on load
- **Caching Layer**: Redis cluster for high-availability caching

### Vertical Scaling

#### When to Scale Up

Scale vertically when you see:
- High CPU usage (> 80% sustained)
- Memory pressure (> 85% usage)
- Database response times increasing
- Queue backlogs growing

#### Scaling Process

1. **Monitor Current Usage**: Establish baseline metrics
2. **Identify Bottlenecks**: CPU, memory, I/O, or network
3. **Scale Incrementally**: Add resources gradually
4. **Test Performance**: Verify improvements
5. **Monitor Results**: Ensure scaling was effective

## 🚨 Troubleshooting Performance Issues

### Common Performance Problems

#### Slow Query Performance

**Symptoms**: Long response times, high CPU usage
**Diagnosis**:
```sql
-- Find slow queries
SELECT * FROM mysql.slow_log 
WHERE start_time > DATE_SUB(NOW(), INTERVAL 1 HOUR);
```

**Solutions**:
- Add appropriate indexes
- Optimize query filters
- Consider query result caching
- Review data access patterns

#### Memory Leaks

**Symptoms**: Gradually increasing memory usage
**Diagnosis**:
```bash
# Monitor memory over time
watch -n 5 'ps aux | grep frappe'
```

**Solutions**:
- Restart workers regularly
- Review custom code for memory leaks
- Optimize data loading patterns
- Consider memory profiling

#### Plugin Performance Issues

**Symptoms**: Specific tools running slowly
**Diagnosis**:
```python
# Check audit logs for slow operations
frappe.db.sql("""
    SELECT tool_name, AVG(execution_time) as avg_time
    FROM `tabAssistant Audit Log`
    WHERE creation >= CURDATE()
    GROUP BY tool_name
    ORDER BY avg_time DESC
""")
```

**Solutions**:
- Disable unused plugins
- Optimize plugin configurations
- Review plugin code for inefficiencies
- Consider plugin-specific caching

### Performance Testing

#### Load Testing

Use tools like Apache Bench or Artillery:

```bash
# Simple load test
ab -n 1000 -c 10 http://yoursite.com/api/method/frappe_assistant_core.api.admin_api.ping

# More comprehensive testing with Artillery
artillery quick --count 10 --num 100 http://yoursite.com/api/method/frappe_assistant_core.api.admin_api.get_usage_statistics
```

#### Monitoring Tools

Recommended monitoring stack:

- **System Metrics**: Prometheus + Grafana
- **Application Logs**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Database Monitoring**: Percona Monitoring
- **Uptime Monitoring**: UptimeRobot or Pingdom

---

## 📚 Additional Resources

- [Architecture Guide](ARCHITECTURE.md) - System design and scaling patterns
- [API Reference](../api/API_REFERENCE.md) - Detailed API performance characteristics  
- [Security Guide](COMPREHENSIVE_SECURITY_GUIDE.md) - Security performance considerations
- [Technical Documentation](TECHNICAL_DOCUMENTATION.md) - Low-level implementation details

For performance-related support, contact jypaulclinton@gmail.com with your specific use case and current metrics.