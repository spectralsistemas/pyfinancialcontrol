import tkinter as tk
from tkinter import ttk, messagebox
import locale
from datetime import datetime, date
from . import database


# --- Nova Classe para Janelas de Cadastro Genéricas ---
class CadastroItemWindow(tk.Toplevel):
    """
    Janela genérica para cadastrar novos itens (categorias, bancos, cartões).
    """
    def __init__(self, master, item_type: str, callback_on_save):
        super().__init__(master)
        self.item_type = item_type
        self.callback_on_save = callback_on_save
        self.title(f"Cadastrar {item_type.capitalize()}")
        self.geometry("300x150")
        self.transient(master)
        self.grab_set()

        ttk.Label(self, text=f"Nome da {item_type.capitalize()}:").pack(pady=10)
        self.nome_entry = ttk.Entry(self, width=30)
        self.nome_entry.pack(pady=5)
        self.nome_entry.focus_set()

        ttk.Button(self, text="Salvar", command=self.salvar_item).pack(pady=10)

    def salvar_item(self):
        nome = self.nome_entry.get().strip()
        if not nome:
            messagebox.showerror("Erro", "O nome não pode ser vazio.", parent=self)
            return
        try:
            database.adicionar_item_cadastro(self.item_type, nome)
            messagebox.showinfo("Sucesso", f"{self.item_type.capitalize()} '{nome}' adicionada com sucesso!", parent=self)
            self.callback_on_save()
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Erro", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível adicionar a {self.item_type.capitalize()}: {e}", parent=self)


# --- Nova Classe para Janela de Análise ---
class AnaliseFinanceiraWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Análise Financeira Mensal")
        self.geometry("800x600")
        self.transient(master)
        self.grab_set()

        # --- Configuração de Localização (Locale) para Moeda ---
        try:
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
            except locale.Error:
                locale.setlocale(locale.LC_ALL, '')

        # --- Frame de Filtros ---
        frame_filtros = ttk.LabelFrame(self, text="Selecionar Período")
        frame_filtros.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame_filtros, text="Mês:").pack(side='left', padx=5, pady=5)
        self.mes_combo = ttk.Combobox(frame_filtros, values=list(range(1, 13)), width=5, state="readonly")
        self.mes_combo.pack(side='left', padx=5, pady=5)

        ttk.Label(frame_filtros, text="Ano:").pack(side='left', padx=5, pady=5)
        self.ano_entry = ttk.Entry(frame_filtros, width=6)
        self.ano_entry.pack(side='left', padx=5, pady=5)

        ttk.Button(frame_filtros, text="Analisar", command=self.executar_analise).pack(side='left', padx=10, pady=5)

        # --- Frame de Resultados ---
        frame_resultados = ttk.Frame(self)
        frame_resultados.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Resumo Geral (Entradas, Saídas, Saldo) ---
        frame_resumo = ttk.LabelFrame(frame_resultados, text="Resumo do Mês")
        frame_resumo.pack(fill="x", pady=5)
        self.lbl_entradas = ttk.Label(frame_resumo, text="Entradas: R$ 0,00", font=('Helvetica', 12, 'bold'), foreground='green')
        self.lbl_entradas.pack(pady=2)
        self.lbl_saidas = ttk.Label(frame_resumo, text="Saídas: R$ 0,00", font=('Helvetica', 12, 'bold'), foreground='red')
        self.lbl_saidas.pack(pady=2)
        self.lbl_saldo = ttk.Label(frame_resumo, text="Saldo: R$ 0,00", font=('Helvetica', 14, 'bold'))
        self.lbl_saldo.pack(pady=5)

        # --- Detalhes (Categorias e Bancos) ---
        frame_detalhes = ttk.Frame(frame_resultados)
        frame_detalhes.pack(fill="both", expand=True, pady=10)

        # Categoria
        frame_cat = ttk.LabelFrame(frame_detalhes, text="Soma por Categoria")
        frame_cat.pack(side="left", fill="both", expand=True, padx=5)
        self.tree_cat = self.criar_treeview(frame_cat, ("Categoria", "Total"))

        # Banco
        frame_banco = ttk.LabelFrame(frame_detalhes, text="Soma por Banco")
        frame_banco.pack(side="right", fill="both", expand=True, padx=5)
        self.tree_banco = self.criar_treeview(frame_banco, ("Banco", "Total"))

    def criar_treeview(self, parent, columns):
        tree = ttk.Treeview(parent, columns=columns, show='headings')
        tree.heading(columns[0], text=columns[0])
        tree.heading(columns[1], text=columns[1])
        tree.column(columns[0], anchor='w', width=200)
        tree.column(columns[1], anchor='e', width=100)
        tree.pack(fill="both", expand=True)
        return tree

    def executar_analise(self):
        mes_str = self.mes_combo.get()
        ano_str = self.ano_entry.get()

        if not mes_str or not ano_str:
            messagebox.showerror("Erro", "Por favor, selecione o mês e o ano.", parent=self)
            return

        mes = int(mes_str)
        ano = int(ano_str)

        # 1. Atualizar Resumo Geral
        resumo = database.obter_entradas_saidas_saldo(mes, ano)
        self.lbl_entradas.config(text=f"Entradas: {self.formatar_moeda(resumo['entradas'])}")
        self.lbl_saidas.config(text=f"Saídas: {self.formatar_moeda(resumo['saidas'])}")
        self.lbl_saldo.config(text=f"Saldo: {self.formatar_moeda(resumo['saldo'])}")

        # 2. Atualizar Tabelas
        self.popular_tabela(self.tree_cat, database.obter_soma_por_categoria(mes, ano))
        self.popular_tabela(self.tree_banco, database.obter_soma_por_banco(mes, ano))

    def popular_tabela(self, tree, dados):
        for i in tree.get_children():
            tree.delete(i)
        for item in dados:
            tree.insert("", "end", values=(item[0], self.formatar_moeda(item[1])))

    def formatar_moeda(self, valor):
        return locale.currency(valor, grouping=True, symbol=True)

class AppPrincipal:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle Financeiro Pessoal")
        self.root.geometry("1000x600")

        # --- Configuração de Localização (Locale) para Moeda ---
        try:
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
            except locale.Error:
                locale.setlocale(locale.LC_ALL, '')

        self.id_selecionado = None
        self.lancamentos_data = []

        # --- Dicionários para mapear nome -> ID ---
        self.categorias_map = {} # Mapeia nome da categoria para ID
        self.bancos_map = {}     # Mapeia nome do banco para ID
        self.cartoes_map = {}    # Mapeia nome do cartão para ID

        # --- Frames Principais ---
        frame_master = ttk.LabelFrame(root, text="Lançamento")
        frame_master.pack(fill="x", padx=10, pady=5, ipady=5)

        frame_filtros = ttk.LabelFrame(root, text="Filtros da Tabela")
        frame_filtros.pack(fill="x", padx=10, pady=5)

        frame_detail = ttk.Frame(root)
        frame_detail.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Widgets do Frame Master ---
        ttk.Label(frame_master, text="Data (D/M/A):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.data_lancamento_entry = ttk.Entry(frame_master, width=12)
        self.data_lancamento_entry.grid(row=0, column=1, columnspan=2, pady=5, sticky='w')
        self.data_lancamento_entry.insert(0, datetime.now().strftime('%d/%m/%Y')) # Preenche com a data atual

        ttk.Label(frame_master, text="Descrição:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.desc_entry = ttk.Entry(frame_master, width=40)
        self.desc_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='ew')
        
        ttk.Label(frame_master, text="Categoria:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.cat_combo = ttk.Combobox(frame_master, state="readonly")
        self.cat_combo.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky='w')
        ttk.Button(frame_master, text="...", width=3, command=self.abrir_cadastro_categoria).grid(row=2, column=4, padx=2, pady=5, sticky='w')

        ttk.Label(frame_master, text="Banco:").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.banco_combo = ttk.Combobox(frame_master, state="readonly")
        self.banco_combo.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky='w')
        ttk.Button(frame_master, text="...", width=3, command=self.abrir_cadastro_banco).grid(row=3, column=4, padx=2, pady=5, sticky='w')

        ttk.Label(frame_master, text="Cartão:").grid(row=4, column=0, padx=5, pady=5, sticky='w')
        self.cartao_combo = ttk.Combobox(frame_master, state="readonly")
        self.cartao_combo.grid(row=4, column=1, columnspan=3, padx=5, pady=5, sticky='w')
        ttk.Button(frame_master, text="...", width=3, command=self.abrir_cadastro_cartao).grid(row=4, column=4, padx=2, pady=5, sticky='w')

        # --- Validação para campos de valor ---
        vcmd = (self.root.register(self.validar_valor), '%P')

        ttk.Label(frame_master, text="Valor Previsto:").grid(row=0, column=4, padx=15, pady=5, sticky='w')
        self.v_prev_entry = ttk.Entry(frame_master, width=15, justify='right',
                                      validate='key', validatecommand=vcmd)
        self.v_prev_entry.grid(row=0, column=5, padx=5, pady=5, sticky='w')

        ttk.Label(frame_master, text="Valor Pago:").grid(row=1, column=4, padx=15, pady=5, sticky='w')
        self.v_pago_entry = ttk.Entry(frame_master, width=15, justify='right',
                                      validate='key', validatecommand=vcmd)
        self.v_pago_entry.grid(row=1, column=5, padx=5, pady=5, sticky='w')

        self.btn_salvar = ttk.Button(frame_master, text="Salvar Lançamento", command=self.salvar_lancamento)
        self.btn_salvar.grid(row=3, column=5, padx=5, pady=5, sticky='e')
        self.btn_limpar = ttk.Button(frame_master, text="Limpar Campos", command=self.limpar_campos)
        self.btn_limpar.grid(row=4, column=5, padx=5, pady=5, sticky='e')

        # --- Widgets do Frame Filtros ---
        ttk.Label(frame_filtros, text="Mês:").pack(side='left', padx=5, pady=5)
        self.filtro_mes = ttk.Combobox(frame_filtros, values=["Todos"] + list(range(1, 13)), state="readonly")
        self.filtro_mes.pack(side='left', padx=5, pady=5)
        self.filtro_mes.set("Todos")

        self.somente_previsto_var = tk.BooleanVar()
        self.filtro_check = ttk.Checkbutton(frame_filtros, text="Mostrar somente sem valor pago",
                                            variable=self.somente_previsto_var)
        self.filtro_check.pack(side='left', padx=10, pady=5)

        ttk.Button(frame_filtros, text="Filtrar", command=self.atualizar_tabela).pack(side='left', padx=5, pady=5)

        # --- Tabela (Treeview) ---
        cols = ('ID', 'Dia', 'Mês', 'Ano', 'Descrição', 'Categoria', 'Banco', 'Cartão', 'Previsto', 'Pago')
        self.tree = ttk.Treeview(frame_detail, columns=cols, show='headings')

        self.tree.tag_configure('negativo', foreground='red')

        for col in cols:
            self.tree.heading(col, text=col)

        self.tree.column('ID', width=40, anchor='center')
        self.tree.column('Dia', width=40, anchor='center')
        self.tree.column('Mês', width=40, anchor='center')
        self.tree.column('Ano', width=50, anchor='center')
        self.tree.column('Descrição', width=200, anchor='w')
        self.tree.column('Categoria', width=120, anchor='w')
        self.tree.column('Banco', width=120, anchor='w')
        self.tree.column('Cartão', width=120, anchor='w')
        self.tree.column('Previsto', width=100, anchor='e')
        self.tree.column('Pago', width=100, anchor='e')

        scrollbar = ttk.Scrollbar(frame_detail, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)

        self.tree.bind("<Double-1>", self.carregar_para_edicao)

        # --- Botões de Ação Inferiores ---
        frame_acoes = ttk.Frame(root)
        frame_acoes.pack(pady=5)
        ttk.Button(frame_acoes, text="Análise Financeira", command=self.abrir_janela_analise).pack(side='left', padx=10)
        ttk.Button(frame_acoes, text="Excluir Lançamento Selecionado", command=self.excluir_lancamento_selecionado).pack(side='left', padx=10)

        self.carregar_comboboxes()
        self.atualizar_tabela()

    def carregar_comboboxes(self):
        categorias = database.listar_itens_cadastro(database.T_CATEGORIAS)
        self.categorias_map = {cat['nome']: cat['id'] for cat in categorias}
        self.cat_combo['values'] = list(self.categorias_map.keys())
        bancos = database.listar_itens_cadastro(database.T_BANCOS)
        self.bancos_map = {banco['nome']: banco['id'] for banco in bancos}
        self.banco_combo['values'] = list(self.bancos_map.keys())
        cartoes = database.listar_itens_cadastro(database.T_CARTOES)
        self.cartoes_map = {cartao['nome']: cartao['id'] for cartao in cartoes}
        self.cartao_combo['values'] = list(self.cartoes_map.keys())

    def atualizar_tabela(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        mes = self.filtro_mes.get()
        mes = int(mes) if mes != "Todos" else None

        self.lancamentos_data = database.listar_lancamentos_filtrados(
            mes=mes,
            somente_previsto=self.somente_previsto_var.get()
        )

        for lanc in self.lancamentos_data:
            valores = list(lanc)
            tags = []

            # Substitui None por "" para Banco e Cartão
            if valores[6] is None:
                valores[6] = ""
            if valores[7] is None:
                valores[7] = ""

            val_previsto_raw = valores[8]
            if val_previsto_raw is not None:
                try:
                    val_previsto = float(val_previsto_raw)
                    if val_previsto < 0:
                        tags.append('negativo')
                    valores[8] = self.formatar_moeda(val_previsto)
                except (ValueError, TypeError):
                    valores[8] = str(val_previsto_raw)
            else:
                valores[8] = "" # Keep as empty string if None

            val_pago_raw = valores[9]
            if val_pago_raw is not None:
                try:
                    val_pago_float = float(val_pago_raw)
                    if val_pago_float < 0 and 'negativo' not in tags:
                        tags.append('negativo')
                    valores[9] = self.formatar_moeda(val_pago_float)
                except (ValueError, TypeError):
                    valores[9] = str(val_pago_raw)
            else:
                valores[9] = ""

            self.tree.insert("", "end", values=tuple(valores), tags=tags)

    def salvar_lancamento(self):
        if not self.desc_entry.get():
            messagebox.showerror("Erro", "O campo Descrição é obrigatório.")
            return

        data_str = self.data_lancamento_entry.get()
        try:
            dt_obj = datetime.strptime(data_str, '%d/%m/%Y')
            dia = dt_obj.day
            mes = dt_obj.month
            ano = dt_obj.year
        except ValueError:
            messagebox.showerror("Erro", "Formato de data inválido. Use DD/MM/AAAA.")
            return

        dados = {
            'dia': dia, 'mes': mes, 'ano': ano,
            'descricao': self.desc_entry.get(),
            'categoria_id': self.categorias_map.get(self.cat_combo.get()),
            'banco_id': self.bancos_map.get(self.banco_combo.get()),
            'cartao_id': self.cartoes_map.get(self.cartao_combo.get()),
            'valor_previsto': float(self.v_prev_entry.get().strip().replace(',', '.')) if self.v_prev_entry.get().strip() else None,
            'valor_pago': float(self.v_pago_entry.get().strip().replace(',', '.')) if self.v_pago_entry.get().strip() else None
        }

        if self.id_selecionado:
            database.atualizar_lancamento(self.id_selecionado, dados)
        else:
            database.adicionar_lancamento(dados)

        self.limpar_campos()
        self.atualizar_tabela()

    def carregar_para_edicao(self, event):
        item_selecionado = self.tree.focus()
        if not item_selecionado:
            return

        id_selecionado_str = self.tree.item(item_selecionado, 'values')[0]
        self.id_selecionado = int(id_selecionado_str)

        dados_originais = next((lanc for lanc in self.lancamentos_data if lanc[0] == self.id_selecionado), None)

        if not dados_originais:
            messagebox.showerror("Erro", "Não foi possível encontrar os dados originais para edição.")
            return

        # Formata dia, mes, ano em uma única string DD/MM/AAAA
        ano = int(dados_originais[3])
        mes = int(dados_originais[2])
        dia = int(dados_originais[1])
        data_obj = date(ano, mes, dia)
        self.data_lancamento_entry.delete(0, 'end'); self.data_lancamento_entry.insert(0, data_obj.strftime('%d/%m/%Y'))
        self.desc_entry.delete(0, 'end'); self.desc_entry.insert(0, dados_originais[4])
        self.cat_combo.set(dados_originais[5] or "")
        self.banco_combo.set(dados_originais[6] or "")
        self.cartao_combo.set(dados_originais[7] or "")
        
        valor_previsto_raw = dados_originais[8]
        self.v_prev_entry.delete(0, 'end')
        if valor_previsto_raw is not None:
            self.v_prev_entry.insert(0, f"{float(valor_previsto_raw):.2f}".replace('.', ','))
        else:
            self.v_prev_entry.insert(0, "")

        valor_pago_raw = dados_originais[9]
        self.v_pago_entry.delete(0, 'end')
        if valor_pago_raw is not None:
            self.v_pago_entry.insert(0, f"{float(valor_pago_raw):.2f}".replace('.', ','))
        else:
            self.v_pago_entry.insert(0, "")

    def excluir_lancamento_selecionado(self):
        item_selecionado = self.tree.focus()
        if not item_selecionado:
            messagebox.showwarning("Aviso", "Selecione um lançamento para excluir.")
            return

        if messagebox.askyesno("Confirmar", "Tem certeza que deseja excluir o lançamento selecionado?"):
            id_lancamento = self.tree.item(item_selecionado, 'values')[0]
            database.excluir_lancamento(id_lancamento)
            self.atualizar_tabela()
            self.limpar_campos()

    def limpar_campos(self):
        self.id_selecionado = None
        self.data_lancamento_entry.delete(0, 'end'); self.data_lancamento_entry.insert(0, datetime.now().strftime('%d/%m/%Y'))
        self.desc_entry.delete(0, 'end')
        self.cat_combo.set('')
        self.banco_combo.set('')
        self.cartao_combo.set('')
        self.v_prev_entry.delete(0, 'end')
        self.v_pago_entry.delete(0, 'end')
        self.desc_entry.focus()

    def validar_valor(self, P):
        """Função de validação para permitir apenas números, uma vírgula e um sinal de menos no início."""
        if P == "" or P == "-":
            return True
        
        # Permite apenas uma vírgula
        if P.count(',') > 1:
            return False
        
        # Remove o sinal de menos (se houver) e a vírgula para checar se o resto é dígito
        check_val = P.replace(',', '', 1).lstrip('-')
        return check_val.isdigit()

    def formatar_moeda(self, valor):
        """Formata um número como moeda local."""
        if valor is None:
            return ""
        try:
            return locale.currency(valor, grouping=True, symbol=True)
        except (TypeError, ValueError):
            return str(valor)

    # --- Métodos para abrir janelas de cadastro ---
    def abrir_cadastro_categoria(self):
        CadastroItemWindow(self.root, database.T_CATEGORIAS, self.carregar_comboboxes)

    def abrir_cadastro_banco(self):
        CadastroItemWindow(self.root, database.T_BANCOS, self.carregar_comboboxes)

    def abrir_cadastro_cartao(self):
        CadastroItemWindow(self.root, database.T_CARTOES, self.carregar_comboboxes)

    def abrir_janela_analise(self):
        AnaliseFinanceiraWindow(self.root)
