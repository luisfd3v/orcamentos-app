import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from decimal import Decimal, InvalidOperation
import traceback
import sys
import configparser
import os
from database import (get_proximo_numero_orcamento, get_vendedores, get_cliente_por_codigo,
                      get_condicoes_pagamento, get_produto_por_codigo, salvar_orcamento,
                      get_orcamento_cabecalho, get_orcamento_itens, atualizar_orcamento,
                      condicao_permite_sem_cliente, get_deposito_config, get_desconto_config)
from models import Orcamento, ItemOrcamento
from pdf_generator import gerar_pdf_orcamento
from ui.search_window import SearchWindow
from ui.product_search_window import ProductSearchWindow
from ui.desconto_window import DescontoWindow
from ui.vendedor_search_window import VendedorSearchWindow
from ui.condicao_pagamento_search_window import CondicaoPagamentoSearchWindow

def get_config_path():
    """Retorna o caminho para o arquivo de configuração"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        config_path = os.path.join(base_path, 'config.ini')
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_path, 'config', 'config.ini')
    return config_path

def get_fullscreen_setting():
    """Lê a configuração de fullscreen do config.ini"""
    try:
        config = configparser.ConfigParser()
        config_path = get_config_path()
        
        if os.path.exists(config_path):
            config.read(config_path)
            if 'Application' in config and 'fullscreen' in config['Application']:
                return config['Application'].getboolean('fullscreen', fallback=True)
        
        return True
    except Exception as e:
        return True

def get_desconto_padrao_config():
    """Lê o limite de desconto padrão do config.ini"""
    try:
        config = configparser.ConfigParser()
        config_path = get_config_path()
        
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
            if 'Desconto' in config and 'limite_padrao' in config['Desconto']:
                limite = float(config['Desconto']['limite_padrao'])
                return {
                    'desconto_max': limite,
                    'vendedor_encontrado': True,
                    'fonte': 'config.ini'
                }
        
        return None
    except Exception as e:
        return None

def get_terminal_config():
    """Lê o número do terminal do config.ini"""
    try:
        config = configparser.ConfigParser()
        config_path = get_config_path()
        
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
            if 'Application' in config and 'terminal' in config['Application']:
                terminal = config['Application']['terminal']
                return terminal
        
        return "01"  
    except Exception as e:
        return "01"

class MainApplication(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.parent.title("Sistema de Orçamentos")
        
        self.configurar_icone()
        self.configurar_janela()

        self.parent.report_callback_exception = self.handle_exception

        self.cliente_selecionado = None
        self.vendedores_map = {}
        self.cond_pag_map = {}
        self.total_orcamento = Decimal('0.0')
        self.desconto_aplicado = Decimal('0.0')
        self.percentual_desconto = Decimal('0.0')
        self.valor_final = Decimal('0.0')
        self.itens_para_salvar = []
        self.modo_edicao = False
        self.janela_desconto_aberta = False  # Flag para controlar janela de desconto

        self.create_widgets()
        self.setup_keyboard_shortcuts()
        self.novo_orcamento()

    def configurar_icone(self):
        """Configura o ícone da janela para a barra de tarefas"""
        try:
            if getattr(sys, 'frozen', False):
                # Se for executável compilado pelo PyInstaller
                # sys._MEIPASS é o caminho temporário onde o PyInstaller extrai os arquivos
                if hasattr(sys, '_MEIPASS'):
                    base_path = sys._MEIPASS
                else:
                    base_path = os.path.dirname(sys.executable)
                icon_path = os.path.join(base_path, 'ico', 'pedido.ico')
            else:
                # Se estiver rodando o script Python
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                icon_path = os.path.join(base_path, 'ico', 'pedido.ico')
            
            if os.path.exists(icon_path):
                self.parent.iconbitmap(icon_path)
        except Exception as e:
            # Se houver erro ao carregar o ícone, apenas ignore
            pass

    def configurar_janela(self):
        """Configura o tamanho e posição da janela baseado no config.ini"""
        fullscreen = get_fullscreen_setting()
        
        if fullscreen:
            try:
                self.parent.state('zoomed')
            except tk.TclError:
                try:
                    self.parent.attributes('-zoomed', True)
                except tk.TclError:
                    self.parent.geometry(f"{self.parent.winfo_screenwidth()}x{self.parent.winfo_screenheight()}+0+0")
        else:
            width = 900
            height = 600
            
            screen_width = self.parent.winfo_screenwidth()
            screen_height = self.parent.winfo_screenheight()
            
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            self.parent.geometry(f"{width}x{height}+{x}+{y}")
            
            self.parent.minsize(800, 500)

    def setup_keyboard_shortcuts(self):
        """Configura atalhos de teclado"""
        self.parent.bind('<Control-n>', lambda e: self.novo_orcamento())
        self.parent.bind('<Control-s>', lambda e: self.salvar_ou_atualizar_orcamento())
        self.parent.bind('<Control-p>', lambda e: self.gerar_pdf_se_disponivel())
        self.parent.bind('<Control-d>', lambda e: self.abrir_janela_desconto())
        self.parent.bind('<F9>', self.on_f9_search)
        self.parent.bind('<Escape>', self.on_escape_key)
        self.parent.bind('<Delete>', self.on_delete_key)
        
    def gerar_pdf_se_disponivel(self):
        """Gera PDF se houver dados suficientes (atalho Ctrl+P)"""
        if not self.modo_edicao:
            messagebox.showinfo("Informação", "Salve o orçamento primeiro antes de gerar o PDF.")
            return
            
        if not self.items_treeview.get_children():
            messagebox.showinfo("Informação", "Para gerar PDF, é necessário ter pelo menos um item no orçamento.")
            return
            
        self.gerar_pdf_orcamento_atual()
        
    def on_escape_key(self, event):
        """Limpa os campos de produto quando pressiona Escape"""
        self.produto_codigo_entry.delete(0, 'end')
        self.produto_qtd_entry.delete(0, 'end')
        self.produto_codigo_entry.focus()
    
    def on_delete_key(self, event):
        """Exclui item selecionado quando pressiona DELETE"""
        self.excluir_item_selecionado()
        
    def on_f9_search(self, event):
        """
        Busca inteligente com F9 (padrão do sistema legado)
        
        - Se foco no campo cliente: busca cliente
        - Se foco no campo vendedor: busca vendedor
        - Se foco no campo condição pagamento: busca condição pagamento
        - Se foco no campo produto/quantidade: busca produto
        - Outros casos: busca cliente primeiro, depois produto conforme necessário
        """
        current_focus = self.focus_get()
        
        if current_focus == self.cliente_entry or current_focus is None:
            self.open_search_cliente()
        elif current_focus == self.vendedor_entry:
            self.open_search_vendedor()
        elif current_focus == self.cond_pag_entry:
            self.open_search_cond_pagamento()
        elif current_focus in (self.produto_codigo_entry, self.produto_qtd_entry):
            self.open_search_produto()
        elif current_focus == self.numero_orcamento_entry:
            if not self.cliente_selecionado:
                self.open_search_cliente()
            else:
                self.open_search_produto()
        else:
            self.open_search_cliente()

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        error_msg = f"Erro inesperado:\n{exc_type.__name__}: {exc_value}"
        messagebox.showerror("Erro", error_msg)
        
        traceback.print_exception(exc_type, exc_value, exc_traceback)
    
    def carregar_dados_iniciais(self):
        vendedores = get_vendedores()
        if vendedores:
            display_list = [f"{v['codigo']} - {v['nome']}" for v in vendedores]
            self.vendedores_map = {v['codigo']: v for v in vendedores}

        condicoes = get_condicoes_pagamento()
        if condicoes:
            display_list = [f"{c['codigo']} - {c['descricao']}" for c in condicoes]
            self.cond_pag_map = {c['codigo']: c for c in condicoes}
    
    def open_search_cliente(self):
        SearchWindow(self.parent, self.on_cliente_selecionado)

    def on_cliente_selecionado(self, cliente_data):
        self.cliente_selecionado = cliente_data
        self.cliente_var.set(f"{cliente_data['codigo']} - {cliente_data['nome']}")
        if self.focus_get() == self.cliente_entry:
            self.vendedor_entry.focus()
        
        self.atualizar_visibilidade_botao_pdf()

    def on_enter_vendedor(self, event):
        """Valida vendedor e navega para condição de pagamento quando pressiona Enter"""
        self.on_vendedor_focus_out(event)
        self.cond_pag_entry.focus()
        
    def on_enter_cond_pagamento(self, event):
        """Valida condição de pagamento e navega para código do produto quando pressiona Enter"""
        self.on_cond_pag_focus_out(event)
        self.produto_codigo_entry.focus()
        
    def on_enter_quantidade(self, event):
        """Adiciona o item quando pressiona Enter na quantidade"""
        self.adicionar_item()
        
    def on_cliente_focus_out(self, event):
        """Valida o cliente quando o campo perde o foco (mas não força validação)"""
        codigo_cliente = self.cliente_var.get().strip()
        
        if not codigo_cliente:
            self.cliente_selecionado = None
            return
            
        if " - " in codigo_cliente and self.cliente_selecionado:
            expected = f"{self.cliente_selecionado['codigo']} - {self.cliente_selecionado['nome']}"
            if codigo_cliente == expected:
                return
                
        if " - " in codigo_cliente:
            codigo_cliente = codigo_cliente.split(" - ")[0].strip()
        
        cliente = get_cliente_por_codigo(codigo_cliente)
        if cliente:
            self.cliente_selecionado = cliente
            self.cliente_var.set(f"{cliente['codigo']} - {cliente['nome']}")
        else:
            if not " - " in self.cliente_var.get():
                self.cliente_selecionado = None

    def on_enter_cliente(self, event):
        """Valida cliente e navega para vendedor quando pressiona Enter"""
        self.on_cliente_focus_out(event)
        self.vendedor_entry.focus()
    
    def open_search_produto(self):
        ProductSearchWindow(self.parent, self.on_produto_selecionado)

    def on_produto_selecionado(self, produto_data):
        self.produto_codigo_entry.delete(0, 'end')
        self.produto_codigo_entry.insert(0, produto_data['codigo'])
        self.produto_qtd_entry.focus()

    def on_enter_codigo_produto(self, event):
        codigo_produto = self.produto_codigo_entry.get().strip()
        
        if not codigo_produto:
            self.open_search_produto()
            return
            
        try:
            produto = get_produto_por_codigo(codigo_produto.zfill(6))
            if produto:
                self.produto_qtd_entry.focus()
            else:
                messagebox.showwarning("Atenção", f"Produto com código '{codigo_produto}' não encontrado.")
                self.produto_codigo_entry.delete(0, 'end')  
                self.produto_codigo_entry.focus()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao buscar produto: {e}")
            self.produto_codigo_entry.delete(0, 'end')  
            self.produto_codigo_entry.focus()
    
    def on_enter_orcamento(self, event):
        num_orcamento = self.numero_orcamento_entry.get().strip().zfill(6)
        self.carregar_orcamento_existente(num_orcamento)

    def open_search_vendedor(self):
        """Abre janela de seleção de vendedor"""
        VendedorSearchWindow(self.parent, self.on_vendedor_selecionado)
    
    def on_vendedor_selecionado(self, vendedor_data):
        """Callback quando um vendedor é selecionado"""
        self.vendedor_var.set(f"{vendedor_data['codigo']} - {vendedor_data['nome']}")
        self.cond_pag_entry.focus()
    
    def on_vendedor_focus_out(self, event):
        """Valida vendedor ao perder foco"""
        vendedor_texto = self.vendedor_var.get().strip()
        if vendedor_texto:
            codigo = vendedor_texto.split(' - ')[0] if ' - ' in vendedor_texto else vendedor_texto
            codigo = codigo.strip()
            
            vendedor = self.vendedores_map.get(codigo)
            
            if not vendedor and codigo.isdigit():
                codigo_formatado = codigo.zfill(3)
                vendedor = self.vendedores_map.get(codigo_formatado)
            
            if vendedor:
                self.vendedor_var.set(f"{vendedor['codigo']} - {vendedor['nome']}")
            else:
                messagebox.showwarning("Atenção", f"Vendedor com código '{codigo}' não encontrado.")
                self.vendedor_var.set("")

    def open_search_cond_pagamento(self):
        """Abre janela de seleção de condição de pagamento"""
        CondicaoPagamentoSearchWindow(self.parent, self.on_cond_pag_selecionada)
    
    def on_cond_pag_selecionada(self, cond_pag_data):
        """Callback quando uma condição de pagamento é selecionada"""
        self.cond_pag_var.set(f"{cond_pag_data['codigo']} - {cond_pag_data['descricao']}")
        self.produto_codigo_entry.focus()
    
    def on_cond_pag_focus_out(self, event):
        """Valida condição de pagamento ao perder foco"""
        cond_pag_texto = self.cond_pag_var.get().strip()
        if cond_pag_texto:
            codigo = cond_pag_texto.split(' - ')[0] if ' - ' in cond_pag_texto else cond_pag_texto
            codigo = codigo.strip()
            
            cond_pag = self.cond_pag_map.get(codigo)
            
            if not cond_pag and codigo.isdigit():
                codigo_formatado = codigo.zfill(2)
                cond_pag = self.cond_pag_map.get(codigo_formatado)
            
            if cond_pag:
                self.cond_pag_var.set(f"{cond_pag['codigo']} - {cond_pag['descricao']}")
            else:
                messagebox.showwarning("Atenção", f"Condição de pagamento com código '{codigo}' não encontrada.")
                self.cond_pag_var.set("")

    def carregar_orcamento_existente(self, numero_nota):
        cabecalho = get_orcamento_cabecalho(numero_nota)
        if not cabecalho:
            messagebox.showerror("Erro", f"Orçamento nº {numero_nota} não encontrado.")
            self.novo_orcamento()
            return

        self.orcamento_status = cabecalho['status']

        if cabecalho['status'] and cabecalho['status'] != '8':
            resposta = messagebox.askyesno(
                "Orçamento Já Faturado", 
                f"O orçamento nº {numero_nota} já foi faturado/transformado em pedido.\n\n"
                "Não é possível alterar orçamentos que já viraram vendas.\n\n"
                "Deseja reimprimir este orçamento antes de criar um novo?\n\n"
                "Sim = Reimprimir e criar novo\n"
                "Não = Apenas criar novo"
            )
            
            if resposta:  
                self.reimprimir_orcamento_faturado(numero_nota, cabecalho)
            
            self.novo_orcamento()
            self.cliente_entry.focus()
            return

        self.novo_orcamento(limpar_combos=False)
        self.modo_edicao = True
        self.save_button.config(text="Atualizar Orçamento (Ctrl+S)")
        
        self.numero_orcamento_var.set(numero_nota)
        
        cliente = get_cliente_por_codigo(cabecalho['codigo_cliente'])
        if cliente:
            self.on_cliente_selecionado(cliente)
        elif cabecalho['codigo_cliente'].strip():
            messagebox.showwarning(
                "Cliente Não Encontrado", 
                f"Cliente código '{cabecalho['codigo_cliente']}' não encontrado no cadastro.\n"
                "O orçamento será carregado, mas você precisará selecionar um cliente para salvar."
            )

        vendedor_display = f"{cabecalho['codigo_vendedor']} - {self.vendedores_map.get(cabecalho['codigo_vendedor'], {}).get('nome', '')}"
        self.vendedor_var.set(vendedor_display)
        
        cond_pag_display = f"{cabecalho['codigo_cond_pag']} - {self.cond_pag_map.get(cabecalho['codigo_cond_pag'], {}).get('descricao', '')}"
        self.cond_pag_var.set(cond_pag_display)

        itens = get_orcamento_itens(numero_nota)
        desconto_total = Decimal('0.0')
        total_bruto = Decimal('0.0')
        for item in itens:
            item_id = self.items_treeview.insert('', 'end', values=(
                item['codigo'], item['descricao'],
                f"{item['quantidade']:.2f}".replace('.',','), item['unidade'],
                f"{item['preco']:.2f}".replace('.',','), f"{item['subtotal']:.2f}".replace('.',',')
            ))
            self.itens_para_salvar.append({
                'id': item_id, 'codigo': item['codigo'], 'quantidade': item['quantidade'],
                'valor_unitario': item['preco'], 'custo': item['custo'],
                'subtotal': item['subtotal'], 'descricao': item['descricao'], 'unidade': item['unidade']
            })
            total_bruto += item['subtotal']
            if 'desconto' in item:
                desconto_total += item['desconto']
        
        if desconto_total > 0:
            self.desconto_aplicado = desconto_total
            if total_bruto > 0:
                self.percentual_desconto = (desconto_total / total_bruto) * 100
            else:
                self.percentual_desconto = Decimal('0.0')
        
        self.atualizar_total()
        
        self.atualizar_visibilidade_botao_pdf()

    def adicionar_item(self, event=None):
        cod_produto_raw = self.produto_codigo_entry.get().strip()
        qtd_str = self.produto_qtd_entry.get().replace(',', '.').strip()

        if not cod_produto_raw or not qtd_str:
            messagebox.showwarning("Atenção", "Preencha o código do produto e a quantidade.")
            if not cod_produto_raw:
                self.produto_codigo_entry.focus()
            else:
                self.produto_qtd_entry.focus()
            return

        cod_produto = cod_produto_raw.zfill(6)

        try:
            quantidade = Decimal(qtd_str)
            if quantidade <= 0:
                raise ValueError("Quantidade deve ser maior que zero")
        except (InvalidOperation, ValueError) as e:
            messagebox.showerror("Erro", "Quantidade inválida. Use apenas números maiores que zero.")
            self.produto_qtd_entry.delete(0, 'end')
            self.produto_qtd_entry.focus()
            return

        try:
            produto = get_produto_por_codigo(cod_produto)
            if not produto:
                messagebox.showerror("Erro", f"Produto com o código '{cod_produto}' não encontrado.")
                self.produto_codigo_entry.delete(0, 'end')
                self.produto_codigo_entry.focus()
                return
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao buscar produto: {e}")
            self.produto_codigo_entry.focus()
            return

        subtotal = quantidade * produto['preco']
        
        item_id = self.items_treeview.insert('', 'end', values=(
            produto['codigo'],
            produto['descricao'],
            f"{quantidade:.2f}".replace('.',','),
            produto['unidade'],
            f"{produto['preco']:.2f}".replace('.',','),
            f"{subtotal:.2f}".replace('.',',')
        ))

        self.itens_para_salvar.append({
            'id': item_id,
            'codigo': produto['codigo'],
            'quantidade': quantidade,
            'valor_unitario': produto['preco'],
            'custo': produto['custo'],
            'subtotal': subtotal,
            'descricao': produto['descricao'],
            'unidade': produto['unidade']
        })

        self.produto_codigo_entry.delete(0, 'end')
        self.produto_qtd_entry.delete(0, 'end')
        self.produto_codigo_entry.focus()
        self.atualizar_total()
        
        self.atualizar_visibilidade_botao_pdf()

    def atualizar_total(self):
        self.total_orcamento = Decimal('0.0')
        for item_id in self.items_treeview.get_children():
            subtotal_str = self.items_treeview.item(item_id)['values'][5].replace(',', '.')
            self.total_orcamento += Decimal(subtotal_str)
        
        self.valor_final = self.total_orcamento - self.desconto_aplicado
        
        if self.desconto_aplicado > 0:
            total_text = f"TOTAL: R$ {self.total_orcamento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            desconto_text = f" - Desconto: R$ {self.desconto_aplicado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            final_text = f" = FINAL: R$ {self.valor_final:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            self.total_var.set(total_text + desconto_text + final_text)
        else:
            self.total_var.set(f"TOTAL: R$ {self.total_orcamento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    
    def abrir_janela_desconto(self):
        """Abre a janela para aplicar desconto"""
        # Verifica se já existe uma janela de desconto aberta
        if self.janela_desconto_aberta:
            messagebox.showinfo("Aviso", "Já existe uma janela de desconto aberta.")
            return
            
        if self.total_orcamento <= 0:
            messagebox.showwarning("Aviso", "Adicione produtos ao orçamento antes de aplicar desconto.")
            return
        
        # Marca que a janela está aberta
        self.janela_desconto_aberta = True
        
        desconto_vendedor_info = get_desconto_padrao_config()
        
        # Passa o callback de fechamento para resetar a flag
        DescontoWindow(
            self.parent, 
            float(self.total_orcamento), 
            self.aplicar_desconto_callback, 
            desconto_vendedor_info,
            self.resetar_flag_desconto
        )
    
    def resetar_flag_desconto(self):
        """Reseta a flag de janela de desconto aberta"""
        self.janela_desconto_aberta = False
    
    def aplicar_desconto_callback(self, valor_desconto, percentual, valor_final):
        """Callback chamado quando o desconto é aplicado"""
        self.desconto_aplicado = Decimal(str(valor_desconto))
        self.percentual_desconto = Decimal(str(percentual))
        self.valor_final = Decimal(str(valor_final))
        self.atualizar_total()
    
    def limpar_desconto(self):
        """Remove o desconto aplicado"""
        self.desconto_aplicado = Decimal('0.0')
        self.percentual_desconto = Decimal('0.0')
        self.valor_final = self.total_orcamento
        self.atualizar_total()
    
    def excluir_item_selecionado(self):
        """Exclui o item selecionado do orçamento"""
        # Verifica se há item selecionado
        selected_item = self.items_treeview.selection()
        if not selected_item:
            messagebox.showinfo("Informação", "Selecione um item para excluir.")
            return
        
        # Verifica se o orçamento já foi transformado em pedido
        if (self.modo_edicao and hasattr(self, 'orcamento_status') and 
            self.orcamento_status is not None and self.orcamento_status != '' and 
            self.orcamento_status != '8'):
            messagebox.showerror(
                "Operação não permitida", 
                f"Este orçamento já foi faturado/finalizado (Status: {self.orcamento_status}) e não pode ser alterado.\n\n"
                "Não é possível excluir itens de orçamentos que já viraram pedidos."
            )
            return
        
        # Pega informações do item para mostrar na confirmação
        item_id = selected_item[0]
        item_values = self.items_treeview.item(item_id)['values']
        codigo = item_values[0]
        descricao = item_values[1]
        quantidade = item_values[2]
        valor_total = item_values[5]
        
        # Confirmação de exclusão
        resposta = messagebox.askyesno(
            "Confirmar Exclusão",
            f"Deseja realmente excluir este item?\n\n"
            f"Código: {codigo}\n"
            f"Descrição: {descricao}\n"
            f"Quantidade: {quantidade}\n"
            f"Valor Total: R$ {valor_total}",
            icon='warning'
        )
        
        if not resposta:
            return
        
        # Remove da treeview
        self.items_treeview.delete(item_id)
        
        # Remove da lista de itens para salvar
        self.itens_para_salvar = [item for item in self.itens_para_salvar if item['id'] != item_id]
        
        # Atualiza o total
        self.atualizar_total()
        
        # Atualiza visibilidade do botão PDF
        self.atualizar_visibilidade_botao_pdf()
        
        # Foca no campo de produto para facilitar adicionar novo item
        self.produto_codigo_entry.focus()
    
    def on_treeview_right_click(self, event):
        """Mostra menu de contexto ao clicar com botão direito"""
        # Seleciona o item clicado
        item_id = self.items_treeview.identify_row(event.y)
        if item_id:
            self.items_treeview.selection_set(item_id)
            self.items_treeview.focus(item_id)
            
            # Cria menu de contexto
            context_menu = tk.Menu(self.parent, tearoff=0)
            context_menu.add_command(label="Excluir Item", command=self.excluir_item_selecionado)
            
            # Mostra o menu na posição do cursor
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

    def on_treeview_double_click(self, event):
        region = self.items_treeview.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self.items_treeview.identify_column(event.x)
        if column not in ('#3', '#5'):
            return

        item_id = self.items_treeview.focus()
        x, y, width, height = self.items_treeview.bbox(item_id, column)
        entry = ttk.Entry(self.items_treeview)
        entry.place(x=x, y=y, width=width, height=height)
        
        col_index = int(column.replace('#', '')) - 1
        current_value = self.items_treeview.item(item_id, 'values')[col_index]
        entry.insert(0, current_value)
        entry.focus()

        if column == '#5':
            entry.bind("<Return>", lambda e, i=item_id: self.save_cell_edit(e, i, 'price'))
        elif column == '#3':
            entry.bind("<Return>", lambda e, i=item_id: self.save_cell_edit(e, i, 'quantity'))
        
        entry.bind("<FocusOut>", lambda e: e.widget.destroy())

    def save_cell_edit(self, event, item_id, edit_type):
        entry = event.widget
        new_value_str = entry.get().replace(',', '.')

        try:
            new_value = Decimal(new_value_str)
            if new_value < 0: raise ValueError
        except (InvalidOperation, ValueError):
            messagebox.showerror("Erro", "Valor inválido.")
            entry.destroy()
            return

        current_values = list(self.items_treeview.item(item_id, 'values'))
        new_price = Decimal('0.0')
        new_quantity = Decimal('0.0')
        new_subtotal = Decimal('0.0')
        
        if edit_type == 'price':
            quantity = Decimal(current_values[2].replace(',', '.'))
            new_price = new_value
            new_subtotal = new_price * quantity
            current_values[4] = f"{new_price:.2f}".replace('.', ',')
            current_values[5] = f"{new_subtotal:.2f}".replace('.', ',')
        elif edit_type == 'quantity':
            price = Decimal(current_values[4].replace(',', '.'))
            new_quantity = new_value
            new_subtotal = price * new_quantity
            current_values[2] = f"{new_quantity:.2f}".replace('.', ',')
            current_values[5] = f"{new_subtotal:.2f}".replace('.', ',')
        
        self.items_treeview.item(item_id, values=tuple(current_values))
        
        for item in self.itens_para_salvar:
            if item['id'] == item_id:
                if edit_type == 'price':
                    item['valor_unitario'] = new_price
                elif edit_type == 'quantity':
                    item['quantidade'] = new_quantity
                item['subtotal'] = new_subtotal
                break
        
        entry.destroy()
        self.atualizar_total()

    def salvar_ou_atualizar_orcamento(self):
        if not self.items_treeview.get_children():
            messagebox.showwarning("Atenção", "Adicione pelo menos um item ao orçamento.")
            return

        if not self.cliente_selecionado:
            try:
                cond_pag_selecionada_str = self.cond_pag_var.get()
                cod_cond_pag = cond_pag_selecionada_str.split(' - ')[0]
                permite_sem_cliente = condicao_permite_sem_cliente(cod_cond_pag)
                
                if not permite_sem_cliente:
                    messagebox.showerror(
                        "Cliente Obrigatório", 
                        f"A condição de pagamento '{cond_pag_selecionada_str}' exige que um cliente seja informado.\n\n"
                        "Por favor, selecione um cliente antes de salvar o orçamento."
                    )
                    return
                else:
                    if not self.modo_edicao:
                        resposta = messagebox.askyesno(
                            "Cliente Opcional",
                            "Deseja continuar sem informar o cliente?\n\n"
                            "Sim = Continuar sem cliente\n"
                            "Não = Cancelar e selecionar cliente",
                            icon='question'
                        )
                        if not resposta:
                            return
                    else:
                        resposta = messagebox.askyesno(
                            "Cliente Não Informado",
                            f"Este orçamento não possui cliente informado.\n"
                            f"Condição: '{cond_pag_selecionada_str}'\n\n"
                            "Deseja salvar mesmo assim?\n\n"
                            "Sim = Salvar sem cliente (compatível com sistema legado)\n"
                            "Não = Cancelar e selecionar cliente"
                        )
                        if not resposta:
                            return
                            
            except Exception as e:
                messagebox.showerror(
                    "Erro", 
                    f"Erro ao verificar condição de pagamento: {e}\n\n"
                    "Por segurança, um cliente deve ser selecionado."
                )
                return

        if (self.modo_edicao and hasattr(self, 'orcamento_status') and 
            self.orcamento_status is not None and self.orcamento_status != '' and 
            self.orcamento_status != '8'):
            messagebox.showerror(
                "Orçamento Já Faturado", 
                f"Este orçamento já foi faturado/finalizado (Status: {self.orcamento_status}) e não pode ser alterado.\n\nPara fazer alterações, crie um novo orçamento."
            )
            return

        try:
            numero_nota = self.numero_orcamento_var.get()
            
            vendedor_selecionado_str = self.vendedor_var.get()
            cod_vendedor = vendedor_selecionado_str.split(' - ')[0]
            vendedor_obj = self.vendedores_map.get(cod_vendedor)
            
            cond_pag_selecionada_str = self.cond_pag_var.get()
            cod_cond_pag = cond_pag_selecionada_str.split(' - ')[0]

            if not vendedor_obj or not cod_cond_pag:
                raise ValueError("Seleção de vendedor ou condição de pagamento inválida.")

            if self.cliente_selecionado:
                cod_cliente = self.cliente_selecionado['codigo']
            else:
                cod_cliente = ''
            
        except (KeyError, IndexError, TypeError, ValueError) as e:
            messagebox.showerror("Erro", f"Dados do cabeçalho inválidos. Verifique as seleções.\nDetalhe: {e}")
            return

        orcamento_obj = Orcamento(
            numero_nota=numero_nota,
            codigo_cliente=cod_cliente,
            codigo_vendedor=cod_vendedor,
            codigo_cond_pag=cod_cond_pag,
            data_emissao=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            valor_total=self.total_orcamento
        )

        itens_list = []
        for i, item_data in enumerate(self.itens_para_salvar):
            desconto_item = Decimal('0.0')
            if self.desconto_aplicado > 0 and self.total_orcamento > 0:
                proporcao = item_data['subtotal'] / self.total_orcamento
                desconto_item = self.desconto_aplicado * proporcao
            
            item_obj = ItemOrcamento(
                numero_nota=numero_nota,
                sequencia=i + 1,
                codigo_produto=item_data['codigo'],
                quantidade=item_data['quantidade'],
                valor_unitario=item_data['valor_unitario'],
                deposito=get_deposito_config(),
                valor_desconto=desconto_item,
                total_bruto_item=item_data['subtotal'],
                custo=item_data['custo']
            )
            itens_list.append(item_obj)
        
        if self.modo_edicao:
            sucesso, mensagem = atualizar_orcamento(orcamento_obj, itens_list)
        else:
            sucesso, mensagem = salvar_orcamento(orcamento_obj, itens_list)

        if sucesso:
            # Pergunta se deseja imprimir após salvar
            imprimir = messagebox.askyesno(
                "Orçamento Salvo",
                f"{mensagem}\n\nDeseja gerar o PDF do orçamento agora?",
                icon='question'
            )
            
            if imprimir:
                try:
                    cond_pag_descricao = self.cond_pag_var.get()
                    vendedor_obj = self.vendedores_map.get(cod_vendedor)
                    gerar_pdf_orcamento(orcamento_obj, self.itens_para_salvar, self.cliente_selecionado, vendedor_obj, cond_pag_descricao, float(self.desconto_aplicado), float(self.valor_final))
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao gerar PDF: {e}")
            
            self.novo_orcamento()
        else:
            messagebox.showerror("Erro ao Salvar", mensagem)

    def reimprimir_orcamento_faturado(self, numero_nota, cabecalho):
        """Gera PDF de um orçamento já faturado para reimpressão"""
        try:
            cliente = None
            if cabecalho['codigo_cliente'].strip():
                cliente = get_cliente_por_codigo(cabecalho['codigo_cliente'])
                if not cliente:
                    resposta = messagebox.askyesno(
                        "Cliente Não Encontrado",
                        f"Cliente código '{cabecalho['codigo_cliente']}' não encontrado no cadastro.\n\n"
                        "Deseja gerar o PDF mesmo assim usando dados genéricos?\n\n"
                        "Sim = Gerar com 'Cliente Não Informado'\n"
                        "Não = Cancelar reimpressão"
                    )
                    if not resposta:
                        return
            
            if not cliente:
                cliente = {
                    'codigo': cabecalho['codigo_cliente'] if cabecalho['codigo_cliente'].strip() else '00000',
                    'nome': 'Cliente Não Informado',
                    'cpf_cnpj': '',
                    'endereco': '',
                    'telefone': ''
                }
            
            vendedor_obj = self.vendedores_map.get(cabecalho['codigo_vendedor'])
            if not vendedor_obj:
                messagebox.showerror("Erro", "Vendedor não encontrado para reimpressão.")
                return
            
            itens = get_orcamento_itens(numero_nota)
            if not itens:
                messagebox.showerror("Erro", "Itens do orçamento não encontrados.")
                return
            
            itens_para_pdf = []
            for item in itens:
                itens_para_pdf.append({
                    'codigo': item['codigo'],
                    'descricao': item['descricao'],
                    'quantidade': item['quantidade'],
                    'valor_unitario': item['preco'],
                    'custo': item['custo'],
                    'subtotal': item['subtotal'],
                    'unidade': item['unidade']
                })
            
            cond_pag_descricao = self.cond_pag_map.get(cabecalho['codigo_cond_pag'], {}).get('descricao', 'Não informado')
            
            desconto_total = sum(item.get('desconto', 0) for item in itens)
            valor_final = sum(item['subtotal'] for item in itens) - desconto_total
            
            orcamento_obj = Orcamento(
                numero_nota=numero_nota,
                codigo_cliente=cabecalho['codigo_cliente'],
                codigo_vendedor=cabecalho['codigo_vendedor'],
                codigo_cond_pag=cabecalho['codigo_cond_pag'],
                data_emissao=cabecalho.get('data_emissao', datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)),
                valor_total=Decimal(str(valor_final))
            )

            gerar_pdf_orcamento(orcamento_obj, itens_para_pdf, cliente, vendedor_obj, f"{cabecalho['codigo_cond_pag']} - {cond_pag_descricao}", float(desconto_total), float(valor_final))
            messagebox.showinfo("Reimpressão", f"PDF do orçamento {numero_nota} (FATURADO) gerado com sucesso!")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar reimpressão: {e}")

    def gerar_pdf_orcamento_atual(self):
        """Gera PDF do orçamento atual (já salvo)"""
        if not self.modo_edicao:
            messagebox.showwarning("Atenção", "Este orçamento ainda não foi salvo. Salve primeiro antes de gerar o PDF.")
            return
            
        if not self.items_treeview.get_children():
            messagebox.showwarning("Atenção", "Não há itens no orçamento.")
            return
        
        try:
            numero_nota = self.numero_orcamento_var.get()
            
            vendedor_selecionado_str = self.vendedor_var.get()
            cod_vendedor = vendedor_selecionado_str.split(' - ')[0]
            vendedor_obj = self.vendedores_map.get(cod_vendedor)
            
            cond_pag_selecionada_str = self.cond_pag_var.get()
            cod_cond_pag = cond_pag_selecionada_str.split(' - ')[0]

            if not vendedor_obj or not cod_cond_pag:
                raise ValueError("Seleção de vendedor ou condição de pagamento inválida.")

            if self.cliente_selecionado:
                cod_cliente = self.cliente_selecionado['codigo']
            else:
                cod_cliente = '' 
            
        except (KeyError, IndexError, TypeError, ValueError) as e:
            messagebox.showerror("Erro", f"Dados do cabeçalho inválidos. Verifique as seleções.\nDetalhe: {e}")
            return

        orcamento_obj = Orcamento(
            numero_nota=numero_nota,
            codigo_cliente=cod_cliente,
            codigo_vendedor=cod_vendedor,
            codigo_cond_pag=cod_cond_pag,
            data_emissao=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            valor_total=self.total_orcamento
        )

        try:
            cond_pag_descricao = self.cond_pag_var.get()
            gerar_pdf_orcamento(orcamento_obj, self.itens_para_salvar, self.cliente_selecionado, vendedor_obj, cond_pag_descricao, float(self.desconto_aplicado), float(self.valor_final))
            messagebox.showinfo("Sucesso", "PDF gerado com sucesso!")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar PDF: {e}")

    def atualizar_visibilidade_botao_pdf(self):
        """Controla quando o botão PDF deve estar visível - apenas em orçamentos já salvos"""
        if self.modo_edicao and self.items_treeview.get_children():
            self.pdf_button.pack(side="right", padx=5, before=self.save_button)
        else:
            self.pdf_button.pack_forget()

    def novo_orcamento(self, limpar_combos=True):
        for i in self.items_treeview.get_children():
            self.items_treeview.delete(i)
        
        self.itens_para_salvar.clear()
        self.cliente_var.set("")
        self.vendedor_var.set("")  
        self.cond_pag_var.set("")  
        self.cliente_selecionado = None
        self.limpar_desconto()
        self.atualizar_total()
        
        if limpar_combos:
            self.carregar_dados_iniciais()
        
        numero = get_proximo_numero_orcamento()
        self.numero_orcamento_var.set(numero)
        self.cliente_entry.focus()
        self.modo_edicao = False
        self.save_button.config(text="Salvar Orçamento (Ctrl+S)", state="normal")
        self.add_button.config(state="normal")
        
        self.atualizar_visibilidade_botao_pdf()
        
        self.orcamento_status = None

    def create_widgets(self):
        header_frame = ttk.LabelFrame(self.parent, text="Dados do Orçamento", padding=(10, 5))
        header_frame.pack(side="top", fill="x", padx=10, pady=5)

        ttk.Label(header_frame, text="Nº Orçamento:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        orcamento_frame = ttk.Frame(header_frame)
        orcamento_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        self.numero_orcamento_var = tk.StringVar()
        self.numero_orcamento_entry = ttk.Entry(orcamento_frame, textvariable=self.numero_orcamento_var, width=10)
        self.numero_orcamento_entry.pack(side="left")
        self.numero_orcamento_entry.bind("<Return>", self.on_enter_orcamento)
        
        terminal_numero = get_terminal_config()
        terminal_label = ttk.Label(orcamento_frame, text=f" [Tr.{terminal_numero}]", 
                                 font=("Arial", 8), foreground="#666666")
        terminal_label.pack(side="left")

        self.data_emissao_var = tk.StringVar()
        data_formatada = datetime.now().strftime("%d/%m/%Y")
        self.data_emissao_var.set(data_formatada)
        ttk.Label(header_frame, textvariable=self.data_emissao_var, font=("Arial", 10)).grid(row=0, column=4, padx=5, pady=5, sticky="e")

        ttk.Label(header_frame, text="Cliente:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        self.cliente_var = tk.StringVar()
        self.cliente_entry = ttk.Entry(header_frame, textvariable=self.cliente_var, width=40)
        self.cliente_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        self.cliente_entry.bind("<Return>", self.on_enter_cliente)
        self.cliente_entry.bind("<FocusOut>", self.on_cliente_focus_out)
        
        search_button = ttk.Button(header_frame, text="... (F9)", width=8, command=self.open_search_cliente)
        search_button.grid(row=1, column=4, padx=5, pady=5)

        ttk.Label(header_frame, text="Vendedor:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.vendedor_var = tk.StringVar()
        self.vendedor_entry = ttk.Entry(header_frame, textvariable=self.vendedor_var, width=40)
        self.vendedor_entry.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        self.vendedor_entry.bind("<Return>", self.on_enter_vendedor)
        self.vendedor_entry.bind("<FocusOut>", self.on_vendedor_focus_out)
        
        search_vendedor_button = ttk.Button(header_frame, text="... (F9)", width=8, command=self.open_search_vendedor)
        search_vendedor_button.grid(row=2, column=4, padx=5, pady=5)

        ttk.Label(header_frame, text="Cond. Pagamento:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.cond_pag_var = tk.StringVar()
        self.cond_pag_entry = ttk.Entry(header_frame, textvariable=self.cond_pag_var, width=40)
        self.cond_pag_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        self.cond_pag_entry.bind("<Return>", self.on_enter_cond_pagamento)
        self.cond_pag_entry.bind("<FocusOut>", self.on_cond_pag_focus_out)
        
        search_cond_pag_button = ttk.Button(header_frame, text="... (F9)", width=8, command=self.open_search_cond_pagamento)
        search_cond_pag_button.grid(row=3, column=4, padx=5, pady=5)
        
        header_frame.columnconfigure(1, weight=1)

        items_frame = ttk.LabelFrame(self.parent, text="Itens do Orçamento", padding=(10, 5))
        items_frame.pack(expand=True, fill="both", padx=10, pady=5)

        add_item_frame = ttk.Frame(items_frame)
        add_item_frame.pack(fill='x', pady=5)

        ttk.Label(add_item_frame, text="Cód. Produto:").pack(side='left', padx=(0, 5))
        self.produto_codigo_entry = ttk.Entry(add_item_frame, width=15)
        self.produto_codigo_entry.pack(side='left', padx=5)
        self.produto_codigo_entry.bind("<Return>", self.on_enter_codigo_produto)

        search_prod_button = ttk.Button(add_item_frame, text="... (F9)", width=8, command=self.open_search_produto)
        search_prod_button.pack(side='left', padx=5)

        ttk.Label(add_item_frame, text="Quantidade:").pack(side='left', padx=5)
        self.produto_qtd_entry = ttk.Entry(add_item_frame, width=10)
        self.produto_qtd_entry.pack(side='left', padx=5)
        self.produto_qtd_entry.bind("<Return>", self.on_enter_quantidade)

        self.add_button = ttk.Button(add_item_frame, text="Adicionar Item", command=self.adicionar_item)
        self.add_button.pack(side='left', padx=10)

        columns = ('cod', 'desc', 'qtd', 'un', 'vlr_unit', 'vlr_total')
        self.items_treeview = ttk.Treeview(items_frame, columns=columns, show='headings')
        self.items_treeview.bind("<Double-1>", self.on_treeview_double_click)
        self.items_treeview.bind("<Button-3>", self.on_treeview_right_click)  # Botão direito do mouse
        
        self.items_treeview.heading('cod', text='Código')
        self.items_treeview.heading('desc', text='Descrição')
        self.items_treeview.heading('qtd', text='Qtd.')
        self.items_treeview.heading('un', text='UN')
        self.items_treeview.heading('vlr_unit', text='Vlr. Unitário')
        self.items_treeview.heading('vlr_total', text='Vlr. Total')

        self.items_treeview.column('cod', width=80, anchor='center')
        self.items_treeview.column('desc', width=300)
        self.items_treeview.column('qtd', width=80, anchor='e')
        self.items_treeview.column('un', width=50, anchor='center')
        self.items_treeview.column('vlr_unit', width=100, anchor='e')
        self.items_treeview.column('vlr_total', width=100, anchor='e')
        
        self.items_treeview.pack(expand=True, fill='both')

        footer_frame = ttk.Frame(self.parent, padding=(10, 5))
        footer_frame.pack(side="bottom", fill="x", padx=10, pady=5)

        total_frame = ttk.Frame(footer_frame)
        total_frame.pack(side="left")
        
        self.total_var = tk.StringVar(value="TOTAL: R$ 0,00")
        ttk.Label(total_frame, textvariable=self.total_var, font=("Arial", 14, "bold")).pack(side="left")
        
        desconto_config = get_desconto_config()
        if desconto_config.get('habilitar_desconto', True):
            self.desconto_button = ttk.Button(total_frame, text="Desconto (Ctrl+D)", 
                                            command=self.abrir_janela_desconto, width=18)
            self.desconto_button.pack(side="left", padx=(10, 0))

        self.save_button = ttk.Button(footer_frame, text="Salvar Orçamento (Ctrl+S)", command=self.salvar_ou_atualizar_orcamento)
        self.save_button.pack(side="right", padx=5)

        self.pdf_button = ttk.Button(footer_frame, text="Gerar PDF (Ctrl+P)", command=self.gerar_pdf_orcamento_atual)
        self.pdf_button.pack(side="right", padx=5)

        new_button = ttk.Button(footer_frame, text="Novo Orçamento (Ctrl+N)", command=self.novo_orcamento)
        new_button.pack(side="right")
