"""
Mani 272 - Complete System Startup
Starts: Flask Web + Discord Bot + MITM Proxy (Port 9516)
"""

import subprocess
import sys
import os
import time
import signal

def terminate_process(p):
    """Terminate process gracefully"""
    try:
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
    except Exception:
        pass

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # File paths
    app_script = os.path.join(script_dir, "app.py")
    mitm_addon = os.path.join(script_dir, "mitmproxyutils.py")
    cert_dir = os.path.join(script_dir, "certs")
    
    # Validate files exist
    if not os.path.exists(app_script):
        print(f"Error: app.py not found at {app_script}")
        sys.exit(1)
    
    if not os.path.exists(mitm_addon):
        print(f"Error: mitmproxyutils.py not found at {mitm_addon}")
        sys.exit(1)
    
    if not os.path.isdir(cert_dir):
        print(f"Error: certs directory not found at {cert_dir}")
        sys.exit(1)
    
    # MITM Proxy command (Port 9516 for exe compatibility)
    mitm_cmd = [
        "mitmdump",
        "-s", mitm_addon,
        "-p", "9516",
        "--listen-host", "0.0.0.0",
        "--set", "block_global=false",
        "--set", f"confdir={cert_dir}"
    ]
    
    # Flask + Discord Bot command
    app_cmd = [sys.executable, app_script]
    
    mitm_proc = None
    app_proc = None
    
    print("=" * 60)
    print("Mani 272 - COMPLETE SYSTEM STARTUP")
    print("=" * 60)
    print(f"Flask Web Dashboard: http://127.0.0.1:5000")
    print(f"Network Access: http://10.197.70.127:5000")
    print(f"MITM Proxy: http://10.197.70.127:9516")
    print(f"Discord Bot: Starting...")
    print("=" * 60)
    
    try:
        # Start Flask + Discord Bot
        print("\n[1/2] Starting Flask Web + Discord Bot...")
        app_proc = subprocess.Popen(app_cmd)
        time.sleep(2)
        print(f"✓ Flask + Bot started (PID: {app_proc.pid})")
        
        # Start MITM Proxy
        print("\n[2/2] Starting MITM Proxy on port 9516...")
        mitm_proc = subprocess.Popen(mitm_cmd)
        time.sleep(2)
        print(f"✓ MITM Proxy started (PID: {mitm_proc.pid})")
        
        print("\n" + "=" * 60)
        print("ALL SYSTEMS ONLINE!")
        print("=" * 60)
        print("\nEXE Configuration:")
        print("  Proxy IP: 10.197.70.127")
        print("  Proxy Port: 9516")
        print("  Proxy URL: http://10.197.70.127:9516")
        print("\nPress Ctrl+C to stop all services...")
        print("=" * 60)
        
        # Monitor processes
        while True:
            if mitm_proc.poll() is not None:
                print("\n⚠ MITM Proxy stopped unexpectedly!")
                break
            if app_proc.poll() is not None:
                print("\n⚠ Flask/Bot stopped unexpectedly!")
                break
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\nReceived shutdown signal...")
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure 'mitmdump' is installed:")
        print("  pip install mitmproxy")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("\nShutting down services...")
        terminate_process(mitm_proc)
        terminate_process(app_proc)
        print("✓ All services stopped")
        print("Goodbye!")

if __name__ == "__main__":
    main()
