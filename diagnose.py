#!/usr/bin/env python3
"""
Render Deployment Diagnostics Script
Ejecuta verificaciones para detectar problemas comunes en deployment
"""

import sys
import os
import json
import subprocess
from datetime import datetime

def log(message, level="INFO"):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {level}: {message}")

def check_python():
    log(f"Python version: {sys.version}")
    log(f"Python path: {sys.executable}")
    return True

def check_environment():
    log("Environment variables:")
    important_vars = ['PORT', 'RENDER', 'RENDER_SERVICE_NAME', 'FLASK_ENV', 'PYTHON_VERSION']
    for var in important_vars:
        value = os.environ.get(var, 'NOT SET')
        log(f"  {var} = {value}")
    return True

def check_dependencies():
    log("Checking critical dependencies:")
    critical_deps = ['flask', 'yt-dlp', 'gunicorn']
    
    for dep in critical_deps:
        try:
            result = subprocess.run([sys.executable, '-c', f'import {dep.replace("-", "_")}; print({dep.replace("-", "_")}.__version__)'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                log(f"  ✅ {dep}: {result.stdout.strip()}")
            else:
                log(f"  ❌ {dep}: Failed to import", "ERROR")
        except Exception as e:
            log(f"  ❌ {dep}: {e}", "ERROR")
    
    return True

def check_flask_app():
    log("Testing Flask application:")
    try:
        # Import app without starting server
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app import app
        
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/health')
            log(f"  Health check: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                log(f"  Health data: {json.dumps(data, indent=2)}")
            
            # Test API status
            response = client.get('/api/status')
            log(f"  API status: {response.status_code}")
            
            # Test main page
            response = client.get('/')
            log(f"  Main page: {response.status_code}")
            
        log("  Flask app tests completed")
        return True
        
    except Exception as e:
        log(f"  Flask app test failed: {e}", "ERROR")
        return False

def main():
    log("🔍 Starting Render Deployment Diagnostics")
    log("=" * 50)
    
    checks = [
        ("Python Environment", check_python),
        ("Environment Variables", check_environment), 
        ("Dependencies", check_dependencies),
        ("Flask Application", check_flask_app)
    ]
    
    results = {}
    for name, check_func in checks:
        log(f"\n📋 Running: {name}")
        try:
            results[name] = check_func()
            log(f"✅ {name}: PASSED")
        except Exception as e:
            results[name] = False
            log(f"❌ {name}: FAILED - {e}", "ERROR")
    
    log("\n" + "=" * 50)
    log("📊 DIAGNOSTIC SUMMARY:")
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"  {name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        log("🎉 All diagnostics passed! App should work correctly.")
    else:
        log("⚠️ Some diagnostics failed. Check errors above.", "WARNING")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())