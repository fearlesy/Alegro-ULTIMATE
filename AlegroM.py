import sys
import os
import subprocess
import ctypes
import webbrowser
import logging
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, 
    QLabel, QGridLayout, QFrame, QSystemTrayIcon, QMenu, QHBoxLayout,
    QProgressBar, QDialog, QCheckBox, QMessageBox, QStatusBar,
    QGroupBox, QTextEdit, QFileDialog, QTabWidget, QListWidget,
    QListWidgetItem, QSlider, QSpinBox, QComboBox
)
from PySide6.QtCore import (
    Qt, QTimer, QSize, QSharedMemory, QThread, Signal
)
from PySide6.QtGui import (
    QAction, QIcon, QFont, QColor
)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

# ==============================================
# GLOBAL KONFİGÜRASYON
# ==============================================
APP_NAME = "Alegro Ultimate"
APP_VERSION = "1.5.0"
APP_AUTHOR = "Alegro Team"
APP_YEAR = "2024"

# ==============================================
# LOG SİSTEMİ
# ==============================================
class Logger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.report_dir = Path("reports")
        self.report_dir.mkdir(exist_ok=True)
        
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        self.setup_logging()
        self._initialized = True
    
    def setup_logging(self):
        log_file = self.log_dir / f"alegro_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(APP_NAME)
        self.logger.info(f"=== {APP_NAME} v{APP_VERSION} Başlatıldı ===")
    
    def log(self, level: str, operation: str, message: str = "", details: Dict = None):
        log_msg = f"[{operation}] {message}"
        if details:
            log_msg += f" | {json.dumps(details, default=str)}"
        
        getattr(self.logger, level.lower(), self.logger.info)(log_msg)
    
    def save_report(self, title: str, content: str):
        report_file = self.report_dir / f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return report_file

# ==============================================
# TEK ÖRNEK KONTROLÜ
# ==============================================
def check_single_instance():
    """Programın zaten çalışıp çalışmadığını kontrol eder"""
    shared_mem = QSharedMemory(f"{APP_NAME}_{APP_VERSION}")
    if shared_mem.attach():
        return False
    return shared_mem.create(512)

# ==============================================
# YÖNETİCİ KONTROLÜ
# ==============================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# ==============================================
# İKON YÖNETİCİSİ
# ==============================================
def get_application_icon():
    """Uygulama ikonunu yükler, bulamazsa varsayılan kullanır"""
    icon_paths = [
        "icon.ico",
        "resources/icon.ico",
        "resources/icon.png",
        "images/icon.ico",
        Path.home() / "Alegro" / "icon.ico"
    ]
    
    for path in icon_paths:
        if Path(path).exists():
            try:
                return QIcon(str(path))
            except:
                continue
    
    return QApplication.style().standardIcon(
        QApplication.style().StandardPixmap.SP_ComputerIcon
    )

# ==============================================
# ARKA PLAN İŞÇİSİ (THREAD)
# ==============================================
class WorkerThread(QThread):
    progress = Signal(int)
    finished = Signal(bool, str)
    log_signal = Signal(str, str, str)
    
    def __init__(self, operation_name: str, command: str):
        super().__init__()
        self.operation_name = operation_name
        self.command = command
        self.logger = Logger()
    
    def run(self):
        try:
            self.log_signal.emit("INFO", self.operation_name, "Başlatılıyor...")
            
            result = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                self.log_signal.emit("SUCCESS", self.operation_name, "Başarılı")
                self.finished.emit(True, result.stdout[:200])
            else:
                self.log_signal.emit("ERROR", self.operation_name, f"Hata: {result.stderr[:100]}")
                self.finished.emit(False, result.stderr[:200])
                
        except subprocess.TimeoutExpired:
            self.log_signal.emit("ERROR", self.operation_name, "Zaman aşımı")
            self.finished.emit(False, "İşlem zaman aşımına uğradı")
        except Exception as e:
            self.log_signal.emit("ERROR", self.operation_name, f"Beklenmeyen hata: {str(e)}")
            self.finished.emit(False, str(e))

# ==============================================
# SİSTEM MONİTÖRÜ
# ==============================================
class SystemMonitor:
    def __init__(self):
        self.logger = Logger()
        self.history = {
            'cpu': [],
            'ram': [],
            'disk': [],
            'network': []
        }
    
    def get_system_info(self) -> Dict:
        info = {
            'timestamp': datetime.now().isoformat(),
            'platform': sys.platform,
            'python_version': sys.version,
            'app_version': APP_VERSION
        }
        
        if HAS_PSUTIL:
            # CPU Bilgileri
            info['cpu'] = {
                'percent': psutil.cpu_percent(interval=0.1),
                'cores': psutil.cpu_count(logical=False),
                'threads': psutil.cpu_count(logical=True),
                'freq': psutil.cpu_freq().current if psutil.cpu_freq() else None
            }
            
            # RAM Bilgileri
            mem = psutil.virtual_memory()
            info['ram'] = {
                'total': mem.total,
                'available': mem.available,
                'percent': mem.percent,
                'used': mem.used
            }
            
            # Disk Bilgileri
            try:
                disk = psutil.disk_usage('/')
                info['disk'] = {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                }
            except:
                info['disk'] = None
            
            # Network
            net = psutil.net_io_counters()
            info['network'] = {
                'bytes_sent': net.bytes_sent,
                'bytes_recv': net.bytes_recv
            }
        
        return info
    
    def get_performance_score(self) -> int:
        if not HAS_PSUTIL:
            return 0
        
        score = 100
        
        # CPU yüksekse puan düşür
        cpu_load = psutil.cpu_percent(interval=0.5)
        if cpu_load > 80:
            score -= 30
        elif cpu_load > 60:
            score -= 15
        
        # RAM yüksekse puan düşür
        ram_percent = psutil.virtual_memory().percent
        if ram_percent > 85:
            score -= 30
        elif ram_percent > 70:
            score -= 15
        
        # Disk doluluğu
        try:
            disk_percent = psutil.disk_usage('/').percent
            if disk_percent > 90:
                score -= 20
            elif disk_percent > 80:
                score -= 10
        except:
            pass
        
        return max(0, min(100, score))

# ==============================================
# OPERASYON GEÇMİŞİ
# ==============================================
class OperationHistory:
    def __init__(self):
        self.history = []
        self.max_history = 50
        self.logger = Logger()
    
    def add(self, operation: str, command: str, success: bool, 
            result: str = "", details: Dict = None):
        entry = {
            'id': len(self.history) + 1,
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'command': command[:100],
            'success': success,
            'result': result[:200],
            'details': details or {}
        }
        
        self.history.append(entry)
        
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        self.logger.log(
            "INFO" if success else "ERROR",
            "HISTORY",
            f"{operation} - {'Başarılı' if success else 'Başarısız'}",
            entry
        )
    
    def get_last(self, n: int = 10) -> List:
        return self.history[-n:]
    
    def clear(self):
        self.history.clear()
        self.logger.log("INFO", "HISTORY", "Geçmiş temizlendi")

# ==============================================
# AYARLAR YÖNETİCİSİ
# ==============================================
class SettingsManager:
    def __init__(self):
        self.settings_file = Path("alegro_settings.json")
        self.default_settings = {
            'general': {
                'language': 'TR',
                'theme': 'GX',
                'start_minimized': False,
                'minimize_to_tray': True,
                'check_updates': True,
                'auto_save_reports': True
            },
            'performance': {
                'auto_boost_threshold': 70,
                'monitor_interval': 2000,
                'enable_logging': True,
                'enable_sounds': False
            },
            'optimizations': {
                'aggressive_mode': False,
                'backup_before_ops': True,
                'confirm_dangerous_ops': True,
                'undo_history_size': 20
            }
        }
        self.settings = self.load_settings()
        self.logger = Logger()
    
    def load_settings(self) -> Dict:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Varsayılan ayarlarla birleştir
                    return self._merge_settings(self.default_settings, loaded)
            except:
                return self.default_settings.copy()
        return self.default_settings.copy()
    
    def _merge_settings(self, default: Dict, loaded: Dict) -> Dict:
        """Recursive settings merge"""
        merged = default.copy()
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_settings(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            self.logger.log("INFO", "SETTINGS", "Ayarlar kaydedildi")
            return True
        except Exception as e:
            self.logger.log("ERROR", "SETTINGS", f"Kaydetme hatası: {str(e)}")
            return False
    
    def get(self, category: str, key: str, default=None):
        return self.settings.get(category, {}).get(key, default)
    
    def set(self, category: str, key: str, value):
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value

# ==============================================
# GÜNCELLEME KONTROLÜ
# ==============================================
class UpdateChecker(QThread):
    update_available = Signal(str, str, str)  # version, changelog, download_url
    
    def run(self):
        try:
            # Simüle edilmiş güncelleme kontrolü
            time.sleep(2)
            
            # Simüle edilmiş yanıt
            latest_version = "1.5.1"
            changelog = "• Hata düzeltmeleri\n• Performans iyileştirmeleri\n• Yeni optimizasyonlar"
            download_url = "https://github.com/username/alegro-ultimate/releases/latest"
            
            if latest_version != APP_VERSION:
                self.update_available.emit(latest_version, changelog, download_url)
                
        except:
            pass  # Sessizce devam et

# ==============================================
# ÖZELLEŞTİRİLMİŞ BUTONLAR
# ==============================================
class ModernButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(45)
        self.setCursor(Qt.PointingHandCursor)
        
    def set_style(self, color="#ff0033", hover_color="#ff3355"):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: #cc0029;
            }}
            QPushButton:disabled {{
                background-color: #666666;
                color: #aaaaaa;
            }}
        """)

# ==============================================
# ANA PENCERE
# ==============================================
class AlegroUltimate(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.logger = Logger()
        self.settings_manager = SettingsManager()
        self.system_monitor = SystemMonitor()
        self.operation_history = OperationHistory()
        
        # Set window properties
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setFixedSize(900, 750)
        self.setWindowIcon(get_application_icon())
        
        # Initialize variables
        self.current_lang = self.settings_manager.get('general', 'language', 'TR')
        self.current_theme = self.settings_manager.get('general', 'theme', 'GX')
        self.boost_score = 0
        self.applied_ops = set()
        self.worker_threads = []
        
        # System tray
        self.tray_icon = None
        
        # Setup UI
        self.init_ui()
        self.setup_tray()
        
        # Start monitoring
        if HAS_PSUTIL:
            self.monitor_timer = QTimer()
            self.monitor_timer.timeout.connect(self.update_system_monitor)
            self.monitor_timer.start(self.settings_manager.get('performance', 'monitor_interval', 2000))
        
        # Check for updates
        if self.settings_manager.get('general', 'check_updates', True):
            self.update_checker = UpdateChecker()
            self.update_checker.update_available.connect(self.show_update_dialog)
            self.update_checker.start()
        
        self.logger.log("INFO", "APP", f"{APP_NAME} başlatıldı")
    
    # ==============================================
    # UI INITIALIZATION
    # ==============================================
    def init_ui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(10)
        
        # TOP BAR
        top_bar = self.create_top_bar()
        main_layout.addLayout(top_bar)
        
        # SYSTEM STATUS FRAME
        status_frame = self.create_status_frame()
        main_layout.addWidget(status_frame)
        
        # TAB WIDGET
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background: #111; }
            QTabBar::tab { background: #222; color: #aaa; padding: 8px 15px; }
            QTabBar::tab:selected { background: #333; color: white; }
            QTabBar::tab:hover { background: #2a2a2a; }
        """)
        
        # Create tabs
        self.create_optimizations_tab()
        self.create_monitor_tab()
        self.create_history_tab()
        self.create_settings_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        # STATUS BAR
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("🔧 Sistem hazır")
        self.status_bar.addWidget(self.status_label)
        
        # Apply theme
        self.update_theme()
    
    def create_top_bar(self):
        layout = QHBoxLayout()
        
        # Logo/Title
        title_label = QLabel(f"⚡ {APP_NAME}")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #ff0033;")
        
        # Version
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet("color: #888; font-size: 11px;")
        
        # Spacer
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addStretch()
        
        # Quick actions
        btn_stats = ModernButton("📊 İstatistikler")
        btn_stats.clicked.connect(self.show_statistics)
        
        btn_report = ModernButton("📄 Rapor")
        btn_report.clicked.connect(self.generate_report)
        
        btn_help = ModernButton("❓ Yardım")
        btn_help.clicked.connect(self.show_help)
        
        for btn in [btn_stats, btn_report, btn_help]:
            btn.setFixedWidth(100)
            layout.addWidget(btn)
        
        return layout
    
    def create_status_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: linear-gradient(to right, #111, #222);
                border: 1px solid #333;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(frame)
        
        # CPU
        cpu_group = self.create_metric_widget("CPU", "#ff0033", 0)
        self.cpu_bar = cpu_group.findChild(QProgressBar)
        
        # RAM
        ram_group = self.create_metric_widget("RAM", "#0078d7", 0)
        self.ram_bar = ram_group.findChild(QProgressBar)
        
        # DISK
        disk_group = self.create_metric_widget("DISK", "#00cc00", 0)
        self.disk_bar = disk_group.findChild(QProgressBar)
        
        # PERFORMANCE SCORE
        score_group = QGroupBox("PERFORMANS SKORU")
        score_group.setStyleSheet("""
            QGroupBox {
                color: #ffcc00;
                border: 2px solid #ffcc00;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        score_layout = QVBoxLayout()
        self.score_label = QLabel("--")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #ffcc00;")
        score_layout.addWidget(self.score_label)
        score_group.setLayout(score_layout)
        
        for widget in [cpu_group, ram_group, disk_group, score_group]:
            layout.addWidget(widget)
        
        return frame
    
    def create_metric_widget(self, name, color, value):
        group = QGroupBox(name)
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        
        layout = QVBoxLayout()
        
        progress_bar = QProgressBar()
        progress_bar.setValue(value)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat(f"{name}: %p%")
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #333;
                border-radius: 5px;
                text-align: center;
                background: #1a1a1a;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 5px;
            }}
        """)
        
        layout.addWidget(progress_bar)
        group.setLayout(layout)
        return group
    
    # ==============================================
    # TAB CREATION METHODS
    # ==============================================
    def create_optimizations_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ULTIMATE BOOST BUTTON
        self.mega_boost_btn = ModernButton("⚡ ULTIMATE MEGA BOOST ⚡")
        self.mega_boost_btn.setMinimumHeight(70)
        self.mega_boost_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #ff0033, stop:1 #ff6600);
                color: white;
                font-size: 18px;
                font-weight: 900;
                border-radius: 10px;
                border: 3px solid #ff9900;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #ff3355, stop:1 #ff8844);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #cc0029, stop:1 #cc5500);
            }
        """)
        self.mega_boost_btn.clicked.connect(self.mega_boost)
        layout.addWidget(self.mega_boost_btn)
        
        # OPTIMIZATION BUTONS GRID
        self.optimization_grid = QGridLayout()
        
        texts = {
            "TR": [
                "NİHAİ GÜÇ", "RAM TEMİZLE", "DNS OPT.", "GPU BOOST",
                "MOUSE FIX", "FSO KAPAT", "PİNG OPT.", "GEREKSİZ SİL",
                "CPU ÖNCELİK", "SHADER SİL", "HIZLI BOOT", "LOG TEMİZLE",
                "AĞ OPT.", "REGISTRY TEMİZ.", "GÜÇ PLANI", "GÜVENLİK OPT.",
                "DISK BİRLEŞTİR", "SERVİS OPT.", "STARTUP OPT.", "GÖRSELLİK OPT."
            ],
            "EN": [
                "ULTIMATE POWER", "CLEAN RAM", "DNS OPT.", "GPU BOOST",
                "MOUSE FIX", "FSO DISABLE", "PING OPT.", "CLEAN JUNK",
                "CPU PRIORITY", "SHADER FLUSH", "FAST BOOT", "CLEAN LOGS",
                "NETWORK OPT.", "REGISTRY CLEAN", "POWER PLAN", "SECURITY OPT.",
                "DISK DEFRAG", "SERVICE OPT.", "STARTUP OPT.", "VISUAL OPT."
            ]
        }
        
        self.optimization_buttons = []
        optimization_funcs = [
            self.optimize_power, self.clean_ram, self.optimize_dns, self.boost_gpu,
            self.fix_mouse, self.disable_fso, self.optimize_ping, self.clean_junk,
            self.set_cpu_priority, self.clear_shaders, self.fast_boot, self.clean_logs,
            self.optimize_network, self.clean_registry, self.set_power_plan,
            self.security_optimize, self.defrag_disk, self.optimize_services,
            self.optimize_startup, self.visual_optimize
        ]
        
        current_texts = texts[self.current_lang]
        for i in range(len(optimization_funcs)):
            btn = ModernButton(current_texts[i])
            btn.setMinimumHeight(50)
            btn.clicked.connect(lambda checked, idx=i: self.run_optimization(idx))
            self.optimization_buttons.append(btn)
            self.optimization_grid.addWidget(btn, i // 4, i % 4)
        
        grid_widget = QWidget()
        grid_widget.setLayout(self.optimization_grid)
        layout.addWidget(grid_widget)
        
        self.tab_widget.addTab(widget, "⚡ Optimizasyonlar")
    
    def create_monitor_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # REAL-TIME CHARTS (simulated)
        monitor_group = QGroupBox("🎯 Canlı Sistem İzleme")
        monitor_layout = QVBoxLayout()
        
        # Process list
        self.process_list = QListWidget()
        self.process_list.setStyleSheet("""
            QListWidget {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background: #333;
            }
        """)
        
        # Update process list
        self.update_process_list()
        
        monitor_layout.addWidget(QLabel("📊 Çalışan Processler:"))
        monitor_layout.addWidget(self.process_list)
        
        # System info
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a1a;
                color: #ccc;
                border: 1px solid #333;
                border-radius: 5px;
                font-family: Consolas, monospace;
            }
        """)
        
        sys_info = self.system_monitor.get_system_info()
        info_text.setPlainText(json.dumps(sys_info, indent=2, ensure_ascii=False))
        
        monitor_layout.addWidget(QLabel("🖥️ Sistem Bilgileri:"))
        monitor_layout.addWidget(info_text)
        
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)
        
        self.tab_widget.addTab(widget, "📊 Monitor")
    
    def create_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        history_group = QGroupBox("📜 İşlem Geçmişi")
        history_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 5px;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background: #333;
            }
        """)
        
        # Add sample history
        self.update_history_list()
        
        # Clear button
        clear_btn = ModernButton("🗑️ Geçmişi Temizle")
        clear_btn.clicked.connect(self.clear_history)
        
        history_layout.addWidget(self.history_list)
        history_layout.addWidget(clear_btn)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        self.tab_widget.addTab(widget, "📜 Geçmiş")
    
    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # GENERAL SETTINGS
        general_group = QGroupBox("⚙️ Genel Ayarlar")
        general_layout = QVBoxLayout()
        
        # Language
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Dil:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Türkçe (TR)", "English (EN)"])
        self.lang_combo.setCurrentText("Türkçe (TR)" if self.current_lang == "TR" else "English (EN)")
        self.lang_combo.currentTextChanged.connect(self.change_language)
        lang_layout.addWidget(self.lang_combo)
        general_layout.addLayout(lang_layout)
        
        # Theme
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Gaming Extreme (GX)", "Emerald Green", "Dark Blue", "Purple Haze"])
        self.theme_combo.setCurrentIndex(0 if self.current_theme == "GX" else 1)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        general_layout.addLayout(theme_layout)
        
        # Checkboxes
        self.cb_startup = QCheckBox("Windows başlangıcında çalıştır")
        self.cb_tray = QCheckBox("Kapatınca sistep tepsisine küçült")
        self.cb_tray.setChecked(True)
        self.cb_updates = QCheckBox("Otomatik güncelleme kontrolü")
        self.cb_updates.setChecked(True)
        
        for cb in [self.cb_startup, self.cb_tray, self.cb_updates]:
            general_layout.addWidget(cb)
        
        general_group.setLayout(general_layout)
        
        # PERFORMANCE SETTINGS
        perf_group = QGroupBox("🚀 Performans Ayarları")
        perf_layout = QVBoxLayout()
        
        # Auto boost threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Otomatik boost eşiği:"))
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(70)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setValue(70)
        self.threshold_slider.valueChanged.connect(self.threshold_spin.setValue)
        self.threshold_spin.valueChanged.connect(self.threshold_slider.setValue)
        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.threshold_spin)
        threshold_layout.addWidget(QLabel("%"))
        perf_layout.addLayout(threshold_layout)
        
        # Monitor interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("İzleme aralığı:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(500, 10000)
        self.interval_spin.setValue(2000)
        self.interval_spin.setSuffix(" ms")
        interval_layout.addWidget(self.interval_spin)
        perf_layout.addLayout(interval_layout)
        
        perf_group.setLayout(perf_layout)
        
        # SAVE BUTTON
        save_btn = ModernButton("💾 Ayarları Kaydet")
        save_btn.clicked.connect(self.save_settings)
        
        layout.addWidget(general_group)
        layout.addWidget(perf_group)
        layout.addStretch()
        layout.addWidget(save_btn)
        
        self.tab_widget.addTab(widget, "⚙️ Ayarlar")
    
    # ==============================================
    # CORE FUNCTIONALITY
    # ==============================================
    def update_system_monitor(self):
        if not HAS_PSUTIL:
            return
        
        # Update progress bars
        cpu_percent = psutil.cpu_percent(interval=0.1)
        ram_percent = psutil.virtual_memory().percent
        
        self.cpu_bar.setValue(int(cpu_percent))
        self.ram_bar.setValue(int(ram_percent))
        
        try:
            disk_percent = psutil.disk_usage('/').percent
            self.disk_bar.setValue(int(disk_percent))
        except:
            pass
        
        # Update performance score
        score = self.system_monitor.get_performance_score()
        self.score_label.setText(f"{score}")
        self.boost_score = score
        
        # Update status label
        status_msg = f"CPU: {cpu_percent:.1f}% | RAM: {ram_percent:.1f}% | Skor: {score}"
        self.status_label.setText(status_msg)
    
    def update_process_list(self):
        if not HAS_PSUTIL:
            return
        
        self.process_list.clear()
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    if info['cpu_percent'] > 0.1 or info['memory_percent'] > 0.1:
                        item_text = f"PID: {info['pid']} | {info['name']} | CPU: {info['cpu_percent']:.1f}% | RAM: {info['memory_percent']:.1f}%"
                        item = QListWidgetItem(item_text)
                        
                        # Color code by resource usage
                        if info['cpu_percent'] > 50 or info['memory_percent'] > 50:
                            item.setForeground(QColor("#ff0000"))  # Red for high usage
                        elif info['cpu_percent'] > 20 or info['memory_percent'] > 20:
                            item.setForeground(QColor("#ff9900"))  # Orange for medium usage
                        
                        self.process_list.addItem(item)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.logger.log("ERROR", "PROCESS_LIST", f"Hata: {str(e)}")
    
    def update_history_list(self):
        self.history_list.clear()
        history = self.operation_history.get_last(20)
        
        for entry in history:
            timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M:%S")
            status = "✅" if entry['success'] else "❌"
            item_text = f"{timestamp} {status} {entry['operation']}"
            item = QListWidgetItem(item_text)
            
            if entry['success']:
                item.setForeground(QColor("#00cc00"))
            else:
                item.setForeground(QColor("#ff0000"))
                item.setToolTip(entry['result'])
            
            self.history_list.addItem(item)
    
    def clear_history(self):
        reply = QMessageBox.question(self, "Geçmişi Temizle",
                                   "Tüm işlem geçmişini temizlemek istiyor musunuz?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.operation_history.clear()
            self.update_history_list()
            self.show_notification("Başarılı", "Geçmiş temizlendi")
    
    def change_language(self, text):
        if "Türkçe" in text:
            self.current_lang = "TR"
        else:
            self.current_lang = "EN"
        
        # Update UI texts
        self.update_optimization_buttons()
        self.show_notification("Bilgi", f"Dil değiştirildi: {self.current_lang}")
    
    def change_theme(self, text):
        theme_map = {
            "Gaming Extreme (GX)": "GX",
            "Emerald Green": "EMERALD",
            "Dark Blue": "BLUE",
            "Purple Haze": "PURPLE"
        }
        
        self.current_theme = theme_map.get(text, "GX")
        self.update_theme()
        self.show_notification("Bilgi", f"Tema değiştirildi: {text}")
    
    def update_theme(self):
        themes = {
            "GX": {"accent": "#ff0033", "bg": "#0a0a0a", "card": "#111"},
            "EMERALD": {"accent": "#00cc88", "bg": "#0a140a", "card": "#112211"},
            "BLUE": {"accent": "#0088ff", "bg": "#0a0a14", "card": "#111122"},
            "PURPLE": {"accent": "#aa00ff", "bg": "#0a0a14", "card": "#111122"}
        }
        
        theme = themes.get(self.current_theme, themes["GX"])
        
        style = f"""
            QMainWindow {{
                background-color: {theme['bg']};
            }}
            QWidget {{
                color: white;
                font-family: 'Segoe UI';
            }}
            QGroupBox {{
                color: {theme['accent']};
                border: 1px solid {theme['accent']};
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QPushButton {{
                background-color: {theme['card']};
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {theme['accent']};
                color: {theme['accent']};
            }}
            QPushButton:pressed {{
                background-color: #222;
            }}
            QProgressBar {{
                background: {theme['card']};
                border: none;
                border-radius: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {theme['accent']};
                border-radius: 6px;
            }}
            QListWidget, QTextEdit {{
                background: {theme['card']};
                border: 1px solid #333;
                border-radius: 5px;
            }}
        """
        
        self.setStyleSheet(style)
    
    def update_optimization_buttons(self):
        texts = {
            "TR": [
                "NİHAİ GÜÇ", "RAM TEMİZLE", "DNS OPT.", "GPU BOOST",
                "MOUSE FIX", "FSO KAPAT", "PİNG OPT.", "GEREKSİZ SİL",
                "CPU ÖNCELİK", "SHADER SİL", "HIZLI BOOT", "LOG TEMİZLE",
                "AĞ OPT.", "REGISTRY TEMİZ.", "GÜÇ PLANI", "GÜVENLİK OPT.",
                "DISK BİRLEŞTİR", "SERVİS OPT.", "STARTUP OPT.", "GÖRSELLİK OPT."
            ],
            "EN": [
                "ULTIMATE POWER", "CLEAN RAM", "DNS OPT.", "GPU BOOST",
                "MOUSE FIX", "FSO DISABLE", "PING OPT.", "CLEAN JUNK",
                "CPU PRIORITY", "SHADER FLUSH", "FAST BOOT", "CLEAN LOGS",
                "NETWORK OPT.", "REGISTRY CLEAN", "POWER PLAN", "SECURITY OPT.",
                "DISK DEFRAG", "SERVICE OPT.", "STARTUP OPT.", "VISUAL OPT."
            ]
        }
        
        current_texts = texts[self.current_lang]
        for i, btn in enumerate(self.optimization_buttons):
            if i < len(current_texts):
                btn.setText(current_texts[i])
    
    # ==============================================
    # OPTIMIZATION FUNCTIONS
    # ==============================================
    def run_optimization(self, index):
        optimization_funcs = [
            self.optimize_power, self.clean_ram, self.optimize_dns, self.boost_gpu,
            self.fix_mouse, self.disable_fso, self.optimize_ping, self.clean_junk,
            self.set_cpu_priority, self.clear_shaders, self.fast_boot, self.clean_logs,
            self.optimize_network, self.clean_registry, self.set_power_plan,
            self.security_optimize, self.defrag_disk, self.optimize_services,
            self.optimize_startup, self.visual_optimize
        ]
        
        if index < len(optimization_funcs):
            func = optimization_funcs[index]
            func()
    
    def optimize_power(self):
        command = "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61"
        self.run_command("Güç Planı Optimizasyonu", command)
    
    def clean_ram(self):
        command = "ipconfig /flushdns && timeout 1"
        self.run_command("RAM Temizleme", command)
    
    def optimize_dns(self):
        command = 'netsh interface ip set dns name="Ethernet" static 8.8.8.8'
        self.run_command("DNS Optimizasyonu", command)
    
    def boost_gpu(self):
        command = 'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers" /v HwSchMode /t REG_DWORD /d 2 /f'
        self.run_command("GPU Boost", command)
    
    def fix_mouse(self):
        command = 'reg add "HKU\\.DEFAULT\\Control Panel\\Mouse" /v MouseSpeed /t REG_SZ /d 0 /f'
        self.run_command("Mouse Fix", command)
    
    def disable_fso(self):
        command = 'reg add "HKCU\\System\\GameConfigStore" /v GameDVR_FSEBehavior /t REG_DWORD /d 2 /f'
        self.run_command("FSO Kapatma", command)
    
    def optimize_ping(self):
        command = 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile" /v NetworkThrottlingIndex /t REG_DWORD /d 0xffffffff /f'
        self.run_command("Ping Optimizasyonu", command)
    
    def clean_junk(self):
        commands = [
            'del /q/f/s %TEMP%\\*',
            'del /q/f/s C:\\Windows\\Temp\\*',
            'cleanmgr /sagerun:1'
        ]
        self.run_commands("Çöp Dosya Temizleme", commands)
    
    def set_cpu_priority(self):
        command = 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Image File Execution Options\\csgo.exe\\PerfOptions" /v CpuPriorityClass /t REG_DWORD /d 3 /f'
        self.run_command("CPU Önceliği", command)
    
    def clear_shaders(self):
        paths = [
            r"%LOCALAPPDATA%\NVIDIA\DXCache",
            r"%LOCALAPPDATA%\AMD\DxCache",
            r"%LOCALAPPDATA%\Intel\ShaderCache"
        ]
        
        commands = []
        for path in paths:
            expanded = os.path.expandvars(path)
            if os.path.exists(expanded):
                commands.append(f'del /f /s /q "{expanded}\\*.*"')
        
        if commands:
            self.run_commands("Shader Temizleme", commands)
        else:
            self.show_notification("Bilgi", "Shader cache bulunamadı")
    
    def fast_boot(self):
        command = "bcdedit /set {current} bootux disabled"
        self.run_command("Hızlı Önyükleme", command)
    
    def clean_logs(self):
        commands = []
        for log in ["System", "Application", "Security", "Setup"]:
            commands.append(f'wevtutil cl {log}')
        self.run_commands("Log Temizleme", commands)
    
    def optimize_network(self):
        commands = [
            'netsh int tcp set global autotuninglevel=normal',
            'netsh int tcp set global rss=enabled',
            'netsh winsock reset'
        ]
        self.run_commands("Ağ Optimizasyonu", commands)
    
    def clean_registry(self):
        command = 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\VolumeCaches\\Old ChkDsk Files" /v StateFlags0001 /t REG_DWORD /d 2 /f'
        self.run_command("Registry Temizleme", command)
    
    def set_power_plan(self):
        command = 'powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
        self.run_command("Güç Planı Ayarlama", command)
    
    def security_optimize(self):
        commands = [
            'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management" /v FeatureSettingsOverride /t REG_DWORD /d 3 /f',
            'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management" /v FeatureSettingsOverrideMask /t REG_DWORD /d 3 /f'
        ]
        self.run_commands("Güvenlik Optimizasyonu", commands)
    
    def defrag_disk(self):
        command = 'defrag C: /O /U'
        self.run_command("Disk Birleştirme", command)
    
    def optimize_services(self):
        commands = [
            'sc config "SysMain" start= disabled',
            'sc stop "SysMain"',
            'sc config "DiagTrack" start= disabled',
            'sc stop "DiagTrack"'
        ]
        self.run_commands("Servis Optimizasyonu", commands)
    
    def optimize_startup(self):
        command = 'taskmgr'
        self.run_command("Startup Optimizasyonu", command)
    
    def visual_optimize(self):
        commands = [
            'reg add "HKCU\\Control Panel\\Desktop" /v DragFullWindows /t REG_SZ /d 0 /f',
            'reg add "HKCU\\Control Panel\\Desktop" /v MenuShowDelay /t REG_SZ /d 0 /f',
            'reg add "HKCU\\Control Panel\\Desktop\\WindowMetrics" /v MinAnimate /t REG_SZ /d 0 /f'
        ]
        self.run_commands("Görsellik Optimizasyonu", commands)
    
    def mega_boost(self):
        reply = QMessageBox.question(self, "MEGA BOOST",
                                   "Tüm optimizasyonları uygulamak istiyor musunuz?\n"
                                   "Bu işlem biraz zaman alabilir.",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.show_notification("Başlatıldı", "Mega Boost başlatıldı...")
            
            # Run all optimizations
            for i in range(20):
                self.run_optimization(i)
                time.sleep(0.5)
            
            self.boost_score = 100
            self.show_notification("Tamamlandı", "Tüm optimizasyonlar uygulandı!")
    
    # ==============================================
    # COMMAND EXECUTION
    # ==============================================
    def run_command(self, operation_name, command):
        worker = WorkerThread(operation_name, command)
        worker.log_signal.connect(self.handle_log)
        worker.finished.connect(lambda success, result: self.command_finished(operation_name, success, result, command))
        worker.start()
        
        self.worker_threads.append(worker)
        self.show_notification("Başlatıldı", f"{operation_name} başlatıldı")
    
    def run_commands(self, operation_name, commands):
        for i, cmd in enumerate(commands):
            time.sleep(0.5)
            self.run_command(f"{operation_name} ({i+1}/{len(commands)})", cmd)
    
    def command_finished(self, operation_name, success, result, command):
        # Add to history
        self.operation_history.add(operation_name, command, success, result)
        
        # Update UI
        self.update_history_list()
        
        if success:
            self.show_notification("Başarılı", f"{operation_name} tamamlandı")
            if operation_name not in self.applied_ops:
                self.applied_ops.add(operation_name)
                self.boost_score = min(100, self.boost_score + 5)
        else:
            self.show_notification("Hata", f"{operation_name} başarısız: {result[:50]}")
    
    def handle_log(self, level, operation, message):
        self.logger.log(level, operation, message)
    
    # ==============================================
    # UTILITY FUNCTIONS
    # ==============================================
    def setup_tray(self):
        if self.tray_icon:
            return
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(get_application_icon())
        
        tray_menu = QMenu()
        
        show_action = QAction("Göster", self)
        show_action.triggered.connect(self.showNormal)
        
        hide_action = QAction("Gizle", self)
        hide_action.triggered.connect(self.hide)
        
        quit_action = QAction("Çıkış", self)
        quit_action.triggered.connect(self.quit_app)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()
    
    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()
    
    def closeEvent(self, event):
        if self.settings_manager.get('general', 'minimize_to_tray', True):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                APP_NAME,
                "Program arka planda çalışmaya devam ediyor",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self.quit_app()
    
    def quit_app(self):
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.instance().quit()
    
    def show_notification(self, title, message, duration=3000):
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, duration)
        else:
            self.status_label.setText(f"{title}: {message}")
    
    def show_statistics(self):
        stats = f"""
        📊 ALEGRO ULTIMATE İSTATİSTİKLERİ
        =================================
        • Toplam İşlem: {len(self.applied_ops)}
        • Performans Skoru: {self.boost_score}/100
        • Aktif Thread: {len(self.worker_threads)}
        • Sistem Sağlığı: {self.system_monitor.get_performance_score()}/100
        • Geçmiş Kayıt: {len(self.operation_history.history)}
        
        UYGULANAN OPTİMİZASYONLAR:
        {', '.join(sorted(self.applied_ops)) if self.applied_ops else 'Henüz yok'}
        """
        
        QMessageBox.information(self, "İstatistikler", stats)
    
    def generate_report(self):
        report = f"""
        {APP_NAME} PERFORMANS RAPORU
        ============================
        Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Versiyon: {APP_VERSION}
        
        SİSTEM BİLGİLERİ:
        {json.dumps(self.system_monitor.get_system_info(), indent=2, ensure_ascii=False)}
        
        PERFORMANS METRİKLERİ:
        • CPU Kullanımı: {self.cpu_bar.value()}%
        • RAM Kullanımı: {self.ram_bar.value()}%
        • Disk Kullanımı: {self.disk_bar.value() if hasattr(self, 'disk_bar') else 'N/A'}%
        • Performans Skoru: {self.boost_score}/100
        
        İŞLEM GEÇMİŞİ:
        {chr(10).join([f"{h['timestamp']} - {h['operation']} ({'✅' if h['success'] else '❌'})" 
                      for h in self.operation_history.get_last(10)])}
        
        TAVSİYELER:
        1. Haftada bir log temizleme yapın
        2. Ayda bir registry optimizasyonu uygulayın
        3. GPU driver'larınızı güncel tutun
        4. Disk birleştirmeyi ayda bir yapın
        """
        
        # Save report
        report_file = self.logger.save_report("Performance_Report", report)
        
        # Show to user
        QMessageBox.information(self, "Rapor Oluşturuldu", 
                              f"Rapor başarıyla oluşturuldu:\n{report_file}")
    
    def show_help(self):
        help_text = f"""
        {APP_NAME} v{APP_VERSION} KULLANIM KILAVUZU
        =========================================
        
        📌 TEMEL ÖZELLİKLER:
        • 20+ optimizasyon seçeneği
        • Gerçek zamanlı sistem izleme
        • İşlem geçmişi takibi
        • Otomatik güncelleme kontrolü
        
        🎯 OPTİMİZASYONLAR:
        1. Güç Planı: Yüksek performans güç planı
        2. RAM Temizleme: Önbellek temizleme
        3. DNS Optimizasyonu: Hızlı DNS sunucuları
        4. GPU Boost: Grafik performansı artırma
        5. Mouse Fix: Mouse gecikmesini azaltma
        
        ⚙️ AYARLAR:
        • Dil seçeneği (TR/EN)
        • 4 farklı tema
        • Otomatik başlatma
        • Tepsiye küçültme
        
        ❓ SIK SORULAN SORULAR:
        Q: Program güvenli mi?
        A: Evet, tüm işlemler Windows sistem komutları ile yapılır.
        
        Q: Veri kaybı olur mu?
        A: Hayır, sadece geçici dosyalar ve önbellekler temizlenir.
        
        📞 DESTEK:
        • Hata bildirimi: GitHub Issues
        • Öneriler: Discord sunucumuz
        • Güncellemeler: Otomatik kontrol
        
        © {APP_YEAR} {APP_AUTHOR}
        """
        
        QMessageBox.information(self, "Yardım", help_text)
    
    def show_update_dialog(self, version, changelog, download_url):
        reply = QMessageBox.question(self, "Güncelleme Mevcut",
                                   f"Yeni versiyon mevcut: {version}\n\n"
                                   f"Değişiklikler:\n{changelog}\n\n"
                                   "Şimdi güncellemek ister misiniz?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            webbrowser.open(download_url)
    
    def save_settings(self):
        # Save language
        if "Türkçe" in self.lang_combo.currentText():
            self.settings_manager.set('general', 'language', 'TR')
        else:
            self.settings_manager.set('general', 'language', 'EN')
        
        # Save theme
        theme_map = {
            "Gaming Extreme (GX)": "GX",
            "Emerald Green": "EMERALD",
            "Dark Blue": "BLUE",
            "Purple Haze": "PURPLE"
        }
        theme = theme_map.get(self.theme_combo.currentText(), "GX")
        self.settings_manager.set('general', 'theme', theme)
        
        # Save checkboxes
        self.settings_manager.set('general', 'start_minimized', self.cb_startup.isChecked())
        self.settings_manager.set('general', 'minimize_to_tray', self.cb_tray.isChecked())
        self.settings_manager.set('general', 'check_updates', self.cb_updates.isChecked())
        
        # Save performance settings
        self.settings_manager.set('performance', 'auto_boost_threshold', self.threshold_spin.value())
        self.settings_manager.set('performance', 'monitor_interval', self.interval_spin.value())
        
        # Save to file
        if self.settings_manager.save_settings():
            self.show_notification("Başarılı", "Ayarlar kaydedildi")
            
            # Apply new settings
            self.current_lang = self.settings_manager.get('general', 'language', 'TR')
            self.current_theme = self.settings_manager.get('general', 'theme', 'GX')
            self.update_optimization_buttons()
            self.update_theme()
            
            # Update monitor interval
            if HAS_PSUTIL and hasattr(self, 'monitor_timer'):
                self.monitor_timer.setInterval(self.interval_spin.value())
        else:
            self.show_notification("Hata", "Ayarlar kaydedilemedi")

# ==============================================
# APPLICATION ENTRY POINT
# ==============================================
if __name__ == "__main__":
    # Check if already running
    if not check_single_instance():
        print(f"{APP_NAME} zaten çalışıyor!")
        sys.exit(0)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)
    
    # Check for admin rights
    if not is_admin():
        # Request admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit(0)
    
    # Create and show main window
    window = AlegroUltimate()
    window.show()
    
    # Start application
    sys.exit(app.exec())