import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from decimal import Decimal, InvalidOperation
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.database import get_desconto_config
except ImportError:
    from database import get_desconto_config


class DescontoWindow:
    def __init__(self, parent, valor_total, callback_desconto=None, desconto_vendedor_info=None, callback_fechar=None):
        self.parent = parent
        self.valor_total = Decimal(str(valor_total))
        self.callback_desconto = callback_desconto
        self.callback_fechar = callback_fechar
        self.desconto_config = get_desconto_config()
        self.desconto_vendedor_info = desconto_vendedor_info or {}
        self.desconto_aplicado = Decimal('0')
        self.valor_final = self.valor_total
        self.updating = False
        
        self.window = tk.Toplevel(parent)
        self.window.title("Sistema de Desconto")
        self.window.geometry("260x440")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Configura protocolo de fechamento
        self.window.protocol("WM_DELETE_WINDOW", self.fechar_janela)
        
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configura a interface da janela de desconto"""
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = ttk.Label(main_frame, text="Sistema de Desconto", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        info_frame = ttk.LabelFrame(main_frame, text="Informações", padding="10")
        info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        ttk.Label(info_frame, text="Valor Total:").grid(row=0, column=0, sticky="w")
        ttk.Label(info_frame, text=f"R$ {self.valor_total:.2f}".replace('.', ','), 
                 font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky="e", padx=(20, 0))
        
        # Mostrar limite configurado
        if self.desconto_vendedor_info and self.desconto_vendedor_info.get('vendedor_encontrado', False):
            limite = self.desconto_vendedor_info.get('desconto_max', 0)
            ttk.Label(info_frame, text="Limite sem senha:").grid(row=1, column=0, sticky="w")
            ttk.Label(info_frame, text=f"{limite:.1f}%", 
                     font=('Arial', 10, 'bold'), foreground='blue').grid(row=1, column=1, sticky="e", padx=(20, 0))
        else:
            ttk.Label(info_frame, text="Limite:").grid(row=1, column=0, sticky="w")
            ttk.Label(info_frame, text="Não configurado", 
                     font=('Arial', 10, 'bold'), foreground='red').grid(row=1, column=1, sticky="e", padx=(20, 0))
        
        desconto_frame = ttk.LabelFrame(main_frame, text="Aplicar Desconto", padding="10")
        desconto_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        ttk.Label(desconto_frame, text="Percentual (%):").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.percentual_var = tk.StringVar()
        self.percentual_var.trace('w', self.on_percentual_change)
        
        self.percentual_entry = ttk.Entry(desconto_frame, textvariable=self.percentual_var, width=15)
        self.percentual_entry.grid(row=0, column=1, sticky="e", padx=(10, 0), pady=(0, 5))
        self.percentual_entry.focus()
        
        ttk.Label(desconto_frame, text="Valor (R$):").grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.valor_var = tk.StringVar()
        self.valor_var.trace('w', self.on_valor_change)
        
        self.valor_entry = ttk.Entry(desconto_frame, textvariable=self.valor_var, width=15)
        self.valor_entry.grid(row=1, column=1, sticky="e", padx=(10, 0), pady=(5, 0))
        
        resultado_frame = ttk.LabelFrame(main_frame, text="Resultado", padding="10")
        resultado_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        ttk.Label(resultado_frame, text="Desconto aplicado:").grid(row=0, column=0, sticky="w")
        self.desconto_label = ttk.Label(resultado_frame, text="R$ 0,00", 
                                      font=('Arial', 10, 'bold'), foreground='red')
        self.desconto_label.grid(row=0, column=1, sticky="e", padx=(20, 0))
        
        ttk.Label(resultado_frame, text="Valor final:").grid(row=1, column=0, sticky="w")
        self.valor_final_label = ttk.Label(resultado_frame, text=f"R$ {self.valor_total:.2f}".replace('.', ','), 
                                         font=('Arial', 12, 'bold'), foreground='blue')
        self.valor_final_label.grid(row=1, column=1, sticky="e", padx=(20, 0))
        
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Aplicar Desconto", 
                  command=self.aplicar_desconto).pack(side="left", padx=(0, 10))
        ttk.Button(buttons_frame, text="Limpar Desconto", 
                  command=self.limpar_desconto).pack(side="left")
        
        main_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)
        desconto_frame.columnconfigure(1, weight=1)
        resultado_frame.columnconfigure(1, weight=1)
        
        self.window.bind('<Return>', lambda e: self.aplicar_desconto())
        
    def safe_decimal(self, value_str):
        """Converte string para Decimal de forma segura"""
        if not value_str:
            return Decimal('0')
        try:
            clean_str = value_str.replace(',', '.').strip()
            if not clean_str:
                return Decimal('0')
            return Decimal(clean_str)
        except (ValueError, InvalidOperation):
            return Decimal('0')
        
    def on_percentual_change(self, *args):
        """Atualiza o campo valor quando percentual muda"""
        if self.updating:
            return
            
        self.updating = True
        try:
            percentual = self.safe_decimal(self.percentual_var.get())
            
            if percentual < 0 or percentual > 100:
                percentual = Decimal('0')
                
            valor_desconto = (self.valor_total * percentual) / Decimal('100')
            
            self.valor_var.set(f"{valor_desconto:.2f}".replace('.', ','))
            
            self.calcular_e_atualizar_resultado(valor_desconto)
            
        except Exception as e:
            pass
        finally:
            self.updating = False
            
    def on_valor_change(self, *args):
        """Atualiza o campo percentual quando valor muda"""
        if self.updating:
            return
            
        self.updating = True
        try:
            valor_desconto = self.safe_decimal(self.valor_var.get())
            
            if valor_desconto < 0 or valor_desconto > self.valor_total:
                if valor_desconto > self.valor_total:
                    valor_desconto = self.valor_total
                    self.valor_var.set(f"{valor_desconto:.2f}".replace('.', ','))
                elif valor_desconto < 0:
                    valor_desconto = Decimal('0')
                    self.valor_var.set("0,00")
                    
            if self.valor_total > 0:
                percentual = (valor_desconto / self.valor_total) * Decimal('100')
            else:
                percentual = Decimal('0')
                
            self.percentual_var.set(f"{percentual:.2f}".replace('.', ','))
            
            self.calcular_e_atualizar_resultado(valor_desconto)
            
        except Exception as e:
            pass
        finally:
            self.updating = False
            
    def calcular_e_atualizar_resultado(self, valor_desconto):
        """Atualiza os labels de resultado"""
        self.desconto_aplicado = valor_desconto
        self.valor_final = self.valor_total - self.desconto_aplicado
        
        self.desconto_label.config(text=f"R$ {self.desconto_aplicado:.2f}".replace('.', ','))
        self.valor_final_label.config(text=f"R$ {self.valor_final:.2f}".replace('.', ','))
            
    def verificar_limite_desconto(self):
        """Verifica se o desconto está dentro do limite permitido"""
        if self.desconto_aplicado == 0:
            return True
            
        percentual_desconto = (self.desconto_aplicado / self.valor_total) * 100 if self.valor_total > 0 else 0
        
        if self.desconto_vendedor_info and self.desconto_vendedor_info.get('vendedor_encontrado', False):
            limite = self.desconto_vendedor_info.get('desconto_max', 0)
        else:
            messagebox.showerror("Erro", "Limite de desconto não configurado no arquivo config.ini.")
            self.percentual_entry.focus_set()
            return False
        
        if percentual_desconto <= limite:
            return True
            
        senha = simpledialog.askstring(
            "Autorização Necessária",
            f"Desconto de {percentual_desconto:.1f}% excede o limite configurado de {limite:.1f}%.\n\nDigite a senha de liberação:",
            show='*',
            parent=self.window
        )
        
        # Se cancelou, retorna foco ao campo
        if senha is None:
            self.percentual_entry.focus_set()
            self.percentual_entry.select_range(0, tk.END)
            return False
        
        # Verifica a senha
        if senha == self.desconto_config['senha_liberacao']:
            return True
        else:
            # Senha incorreta - mostra erro e retorna foco ao campo
            messagebox.showerror(
                "Senha Incorreta",
                "Senha incorreta! Desconto não autorizado.",
                parent=self.window
            )
            self.percentual_entry.focus_set()
            self.percentual_entry.select_range(0, tk.END)
            return False
            
    def aplicar_desconto(self):
        """Aplica o desconto após verificar permissões"""
        if not self.desconto_config['habilitar_desconto']:
            messagebox.showwarning("Aviso", "Sistema de desconto está desabilitado.")
            return
            
        if self.desconto_aplicado == 0:
            messagebox.showwarning("Aviso", "Nenhum desconto foi informado.")
            return
            
        if not self.verificar_limite_desconto():
            return
            
        if self.callback_desconto:
            percentual = (self.desconto_aplicado / self.valor_total) * 100 if self.valor_total > 0 else 0
            self.callback_desconto(float(self.desconto_aplicado), float(percentual), float(self.valor_final))
            
        messagebox.showinfo("Sucesso", 
                          f"Desconto de R$ {self.desconto_aplicado:.2f}".replace('.', ',') + " aplicado com sucesso!\n" +
                          f"Valor final: R$ {self.valor_final:.2f}".replace('.', ','))
        
        self.fechar_janela()

    def limpar_desconto(self):
        """Remove o desconto aplicado e fecha a janela"""
        if self.callback_desconto:
            self.callback_desconto(0.0, 0.0, float(self.valor_total))
            
        messagebox.showinfo("Desconto Removido", "Desconto foi removido com sucesso!")
        self.fechar_janela()
    
    def fechar_janela(self):
        """Fecha a janela e chama o callback de fechamento"""
        if self.callback_fechar:
            self.callback_fechar()
        self.window.destroy()


def main():
    """Função para testar a janela independentemente"""
    root = tk.Tk()
    root.withdraw()
    
    def callback_teste(valor_desconto, percentual, valor_final):
        pass
        
    DescontoWindow(root, 1000.00, callback_teste)
    root.mainloop()


if __name__ == "__main__":
    main()
