import sys
import subprocess
import threading
import time
import os
from datetime import datetime

# Tenta importar bibliotecas, se não tiver instala automático
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def try_import(package, import_name=None):
    import_name = import_name or package
    try:
        return __import__(import_name)
    except ImportError:
        print(f"Pacote '{package}' nao encontrado. Instalando...")
        install_package(package)
        return __import__(import_name)

pyautogui = try_import('pyautogui')
pynput = try_import('pynput')
psutil = try_import('psutil')

from pynput import mouse, keyboard

# Configurações
LOG_FILE = "log.txt"
SCREENSHOTS_DIR = "screenshots"
SCREENSHOT_INTERVAL = 30  # segundos

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Logger thread-safe
log_lock = threading.Lock()

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] {msg}"
    with log_lock:
        print(linha)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha + "\n")

# Monitor teclado
def on_press(key):
    try:
        log(f"Tecla pressionada: {key.char}")
    except AttributeError:
        log(f"Tecla especial pressionada: {key}")

def on_release(key):
    if key == keyboard.Key.esc:
        log("Tecla ESC pressionada. Finalizando monitoramento...")
        return False  # para listener

# Monitor mouse
def on_click(x, y, button, pressed):
    if pressed:
        log(f"Botao do mouse {button} pressionado em ({x}, {y})")

def on_scroll(x, y, dx, dy):
    log(f"Scroll do mouse em ({x}, {y}) delta=({dx}, {dy})")

# Captura de tela periódica
def screenshot_loop():
    while True:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOTS_DIR, f"screenshot_{timestamp}.png")
        try:
            img = pyautogui.screenshot()
            img.save(path)
            log(f"Screenshot salva em: {path}")
        except Exception as e:
            log(f"Erro ao tirar screenshot: {e}")
        time.sleep(SCREENSHOT_INTERVAL)

def main():
    log("Iniciando monitoramento... Pressione ESC para sair.")

    # Threads de monitoramento
    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)

    mouse_listener.start()
    keyboard_listener.start()

    # Thread para screenshots
    t_screenshot = threading.Thread(target=screenshot_loop, daemon=True)
    t_screenshot.start()

    # Espera o teclado terminar (quando ESC for pressionado)
    keyboard_listener.join()

    log("Monitoramento finalizado.")

if __name__ == "__main__":
    main()
