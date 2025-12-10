import tkinter as tk
from tkinter import messagebox
from ui.main_window import MainApplication
import sys
from database import get_db_connection

def verificar_conexao_banco():
    conn = get_db_connection()
    if conn:
        conn.close()
        return True
    return False

if __name__ == "__main__":
    if not verificar_conexao_banco():
        messagebox.showerror(
            "Erro de Conexão", 
            "Não foi possível conectar ao banco de dados.\n"
            "Verifique:\n"
            "- Se o SQL Server está rodando\n"
            "- Se as configurações em config/config.ini estão corretas\n"
            "- Se o driver SQL Server está instalado"
        )
        sys.exit(1)
    
    root = tk.Tk()
    root.withdraw()
    
    app = MainApplication(root)
    app.pack(side="top", fill="both", expand=True)
    
    root.update_idletasks()
    root.deiconify()
    
    root.mainloop()