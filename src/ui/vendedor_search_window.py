import tkinter as tk
from tkinter import ttk
try:
    from database import get_vendedores
except ImportError:
    from src.database import get_vendedores

class VendedorSearchWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Consulta de Vendedores")
        self.geometry("600x400")
        self.callback = callback
        
        self.transient(parent)
        self.grab_set()
        
        self.vendedores_exibidos = []

        self.create_widgets()
        self.filtrar_vendedores()
        
        self.center_window()
        
        self.after(100, lambda: self.search_entry.focus_set())
        
    def center_window(self):
        """Centraliza a janela na tela"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        search_frame = ttk.Frame(self, padding=(10, 5))
        search_frame.pack(fill='x')

        ttk.Label(search_frame, text="Pesquisar:").pack(side='left', padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.filtrar_vendedores)
        self.search_entry.bind("<Return>", self.on_enter_search)
        self.search_entry.bind("<Down>", self.move_to_list)
        self.search_entry.bind("<Up>", self.move_to_list)
        
        self.bind("<Escape>", lambda e: self.destroy())
        
        search_button = ttk.Button(search_frame, text="Filtrar", command=self.filtrar_vendedores)
        search_button.pack(side='left', padx=5)

        columns = ('codigo', 'nome')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=15)
        
        self.tree.heading('codigo', text='Código', anchor='w')
        self.tree.heading('nome', text='Nome', anchor='w')
        
        self.tree.column('codigo', width=80, anchor='w')
        self.tree.column('nome', width=300, anchor='w')
        
        self.tree.pack(expand=True, fill='both', padx=10, pady=5)
        
        self.tree.bind('<Double-1>', self.on_select)
        self.tree.bind('<Return>', self.on_select)
        
        button_frame = ttk.Frame(self, padding=(10, 5))
        button_frame.pack(fill='x')
        
        select_button = ttk.Button(button_frame, text="Selecionar", command=self.on_select)
        select_button.pack(side='right', padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancelar", command=self.destroy)
        cancel_button.pack(side='right', padx=5)

    def filtrar_vendedores(self, event=None):
        """Filtra vendedores baseado na pesquisa"""
        search_text = self.search_entry.get().lower()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        vendedores = get_vendedores()
        self.vendedores_exibidos = []
        
        for vendedor in vendedores:
            codigo = vendedor['codigo'].lower()
            nome = vendedor['nome'].lower()
            
            if (search_text in codigo or search_text in nome or not search_text):
                item = self.tree.insert('', 'end', values=(vendedor['codigo'], vendedor['nome']))
                self.vendedores_exibidos.append(vendedor)
        
        if self.vendedores_exibidos:
            self.tree.selection_set(self.tree.get_children()[0])
            self.tree.focus(self.tree.get_children()[0])

    def on_enter_search(self, event):
        """Seleciona o primeiro item quando pressiona Enter na busca"""
        if self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])
            self.tree.focus(self.tree.get_children()[0])
            self.on_select()

    def move_to_list(self, event):
        """Move o foco para a lista"""
        if self.tree.get_children():
            self.tree.focus(self.tree.get_children()[0])
            self.tree.selection_set(self.tree.get_children()[0])
            self.tree.focus_set()

    def on_select(self, event=None):
        """Callback para seleção de vendedor"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            index = self.tree.index(item)
            if index < len(self.vendedores_exibidos):
                vendedor_selecionado = self.vendedores_exibidos[index]
                self.callback(vendedor_selecionado)
                self.destroy()
