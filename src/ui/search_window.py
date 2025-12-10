import tkinter as tk
from tkinter import ttk
from database import buscar_clientes

class SearchWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Consulta de Clientes")
        self.geometry("700x400")
        self.callback = callback
        
        self.transient(parent)
        self.grab_set()
        
        self.clientes_exibidos = []

        self.create_widgets()
        self.filtrar_clientes()
        
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
        self.search_entry.bind("<KeyRelease>", self.filtrar_clientes)
        self.search_entry.bind("<Return>", self.on_enter_search)
        self.search_entry.bind("<Down>", self.move_to_list)
        self.search_entry.bind("<Up>", self.move_to_list)
        
        self.bind("<Escape>", lambda e: self.destroy())
        
        search_button = ttk.Button(search_frame, text="Filtrar", command=self.filtrar_clientes)
        search_button.pack(side='left', padx=5)

        columns = ('cod', 'cpf_cnpj', 'nome', 'endereco')
        self.treeview = ttk.Treeview(self, columns=columns, show='headings')
        
        self.treeview.heading('cod', text='Código')
        self.treeview.heading('cpf_cnpj', text='CPF/CNPJ')
        self.treeview.heading('nome', text='Nome')
        self.treeview.heading('endereco', text='Endereço')

        self.treeview.column('cod', width=80)
        self.treeview.column('cpf_cnpj', width=120)
        self.treeview.column('nome', width=250)
        self.treeview.column('endereco', width=250)
        
        self.treeview.pack(expand=True, fill='both', padx=10, pady=5)
        self.treeview.bind("<Double-1>", self.on_select)
        self.treeview.bind("<Return>", self.on_select)
        
        footer_frame = ttk.Frame(self, padding=(10, 5))
        footer_frame.pack(fill='x')

        select_button = ttk.Button(footer_frame, text="Selecionar", command=self.on_select)
        select_button.pack(side='right')
        
    def move_to_list(self, event):
        """Move o foco do campo de busca para a lista"""
        if self.treeview.get_children():
            first_item = self.treeview.get_children()[0]
            self.treeview.focus(first_item)
            self.treeview.selection_set(first_item)
            self.treeview.focus_set()
        
    def on_enter_search(self, event):
        """Quando pressiona Enter no campo de busca, seleciona o primeiro item da lista"""
        if self.treeview.get_children():
            first_item = self.treeview.get_children()[0]
            self.treeview.focus(first_item)
            self.treeview.selection_set(first_item)
            self.select_current_item()
            
    def select_current_item(self):
        """Seleciona o item atual da lista"""
        selected_item_id = self.treeview.focus()
        if not selected_item_id:
            return
        
        cliente_data = next((c for c in self.clientes_exibidos if c['codigo'] == selected_item_id), None)

        if cliente_data:
            self.callback(cliente_data)
            self.after_idle(self.destroy)

    def populate_treeview(self):
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        
        for cliente in self.clientes_exibidos:
            self.treeview.insert('', 'end', values=(
                cliente['codigo'], 
                cliente['cpf_cnpj'],
                cliente['nome'], 
                cliente['endereco']
            ), iid=cliente['codigo'])

    def filtrar_clientes(self, event=None):
        """Filtra clientes baseado na pesquisa (código ou nome)"""
        termo_busca = self.search_entry.get()
        
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        
        if termo_busca:
            self.clientes_exibidos = buscar_clientes(termo_inteligente=termo_busca)
        else:
            self.clientes_exibidos = buscar_clientes()
        
        self.populate_treeview()
        
        if self.treeview.get_children():
            first_item = self.treeview.get_children()[0]
            self.treeview.selection_set(first_item)
            self.treeview.focus(first_item)

    def on_select(self, event=None):
        """Seleciona o item da lista (duplo clique ou Enter na lista)"""
        self.select_current_item()
