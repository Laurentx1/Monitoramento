import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageSequence
import subprocess
import os
import sys
import pyautogui

class AppGIF:
    def __init__(self, root):
        self.root = root
        self.root.title("Assistente Mágico")

        # Load GIF background
        try:
            self.gif = Image.open("background.gif")  # Change to your GIF path
            self.frames = [ImageTk.PhotoImage(img) for img in ImageSequence.Iterator(self.gif)]
            self.width, self.height = self.gif.size
            self.root.geometry(f"{self.width}x{self.height}")
        except Exception as e:
            print(f"GIF Error: {e}")
            # Fallback if GIF fails
            self.width, self.height = 400, 500
            self.root.geometry(f"{self.width}x{self.height}")
            self.frames = []
            bg_label = tk.Label(root, text="Assistente Mágico", bg="black", fg="white", font=("Arial", 16))
            bg_label.place(x=0, y=0, width=self.width, height=self.height)

        self.root.resizable(False, False)

        # GIF display label (background)
        self.bg_label = tk.Label(root)
        self.bg_label.place(x=0, y=0, width=self.width, height=self.height)

        # Vertical buttons over GIF
        button_x = 50  # Horizontal position
        self.create_button("📁 Abrir Pasta", button_x, 50, self.abrir_pasta)
        self.create_button("🖱️ Simular F12", button_x, 120, self.simular_f12)
        self.create_button("🚀 Iniciar Monitor", button_x, 190, self.abrir_script)
        self.create_button("❌ Sair", button_x, 260, self.root.quit, width=80, height=30, font_size=10)

        # Start animation if GIF loaded
        if self.frames:
            self.frame_index = 0
            self.animate_gif()

    def create_button(self, text, x, y, command, width=200, height=40, font_size=12):
        btn = tk.Button(self.root, text=text, 
                       font=("Arial", font_size, "bold"),
                       command=command,
                       bg="white",
                       activebackground="#e0e0e0",
                       relief=tk.RAISED,
                       borderwidth=3)
        btn.place(x=x, y=y, width=width, height=height)
        return btn

    def abrir_pasta(self):
        pasta = r"D:\Chrome geral\Zero\NEWWWW\screenshots"
        try:
            if os.path.exists(pasta):
                os.startfile(pasta)
            else:
                messagebox.showerror("Erro", f"Pasta não encontrada:\n{pasta}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao abrir pasta:\n{e}")

    def simular_f12(self):
        try:
            pyautogui.press('f12')
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao pressionar F12:\n{e}")

    def abrir_script(self):
        caminho_script = r"D:\Chrome geral\Zero\NEWWWW\advanced_monitor.py"
        
        if not os.path.exists(caminho_script):
            messagebox.showerror("Erro", f"Arquivo não encontrado:\n{caminho_script}")
            return

        try:
            # Method 1: Direct execution
            subprocess.Popen([sys.executable, caminho_script], shell=True)
            
            # Alternative methods if above fails
            if sys.platform == "win32":
                os.startfile(caminho_script)  # Windows
            else:
                subprocess.Popen(["python3", caminho_script])  # Linux/Mac
                
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao executar script:\n{e}\n\n"
                                     f"Tente executar manualmente:\npython \"{caminho_script}\"")

    def animate_gif(self):
        if self.frames:
            self.bg_label.config(image=self.frames[self.frame_index])
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.root.after(100, self.animate_gif)

if __name__ == "__main__":
    root = tk.Tk()
    app = AppGIF(root)
    root.mainloop()
