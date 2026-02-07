"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Tkinter Desktop Anwendung - Hauptfenster
"""
import tkinter as tk

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Desktop Anwendung")
        self.root.geometry("800x600")
        label = tk.Label(root, text="Willkommen", font=("Arial", 24))
        label.pack(expand=True)

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
