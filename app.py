import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, date, timedelta
from fpdf import FPDF

# ==========================================
# FUNÇÃO PARA GERAR PDF EM MEMÓRIA (fpdf2)
# ==========================================
class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Conslin - Gestão Operacional & Financeira', border=False, ln=True, align='C')
        self.set_font('Arial', 'I', 9)
        self.cell(0, 5, 'Relatório Gerencial Emitido via Sistema', border=False, ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def gerar_pdf_atendimento(cliente_nome, categoria, status, orcamento, fechado, descricao):
    pdf = PDFRelatorio()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Detalhamento do Atendimento / Orçamento", ln=True)
    pdf.ln(3)

    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Cliente: {cliente_nome}", ln=True)
    pdf.cell(0, 6, f"Categoria: {categoria}", ln=True)
    pdf.cell(0, 6, f"Status: {status}", ln=True)
    pdf.cell(0, 6, f"Valor Orçado: R$ {orcamento:,.2f}", ln=True)
    pdf.cell(0, 6, f"Valor Fechado: R$ {fechado:,.2f}", ln=True)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Descrição do Serviço:", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, descricao if descricao else "Sem descrição informada.")

    return bytes(pdf.output())

def gerar_pdf_tabela(titulo, df):
    pdf = PDFRelatorio()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, titulo, ln=True)
    pdf.ln(3)

    pdf.set_font("Arial", "", 9)
    for col in df.columns:
        pdf.cell(38, 7, str(col)[:18], border=1)
    pdf.ln()

    for _, row in df.iterrows():
        for col in df.columns:
            val = str(row[col])
            pdf.cell(38, 6, val[:18], border=1)
        pdf.ln()

    return bytes(pdf.output())

# ==========================================
# FUNÇÕES DE CRIPTOGRAFIA DE SENHA
# ==========================================
def gerar_hash_senha(senha):
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def verificar_senha_hash(senha_digitada, hash_guardado):
    return gerar_hash_senha(senha_digitada) == hash_guardado

# ==========================================
# BANCO DE DADOS
# ==========================================
def conectar():
    return sqlite3.connect("gestao_escritorio.db")

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        perfil TEXT DEFAULT 'Atendente'
    )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        senha_hash_padrao = gerar_hash_senha("conslin123")
        cursor.execute("""
        INSERT INTO usuarios (nome, usuario, senha_hash, perfil)
        VALUES (?, ?, ?, ?)
        """, ("Administrador Conslin", "admin", senha_hash_padrao, "Admin"))
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        telefone TEXT,
        email TEXT,
        cpf_cnpj TEXT,
        endereco TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS atendimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        categoria TEXT NOT NULL,
        descricao TEXT,
        status TEXT NOT NULL,
        valor_orcamento REAL DEFAULT 0.0,
        valor_fechado REAL DEFAULT 0.0,
        despesas REAL DEFAULT 0.0,
        data_contato DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (cliente_id) REFERENCES clientes (id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS metas (
        categoria TEXT PRIMARY KEY,
        meta_valor REAL DEFAULT 0.0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parceiros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL,
        telefone TEXT,
        cpf_cnpj TEXT,
        chave_pix TEXT,
        observacao TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contas_pagar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parceiro_id INTEGER,
        descricao TEXT NOT NULL,
        tipo_conta TEXT NOT NULL,
        valor REAL NOT NULL,
        data_vencimento DATE NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (parceiro_id) REFERENCES parceiros (id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id INTEGER,
        parceiro_id INTEGER,
        valor_pago REAL NOT NULL,
        data_pagamento DATE DEFAULT CURRENT_DATE,
        forma_pagamento TEXT,
        comprovante_ref TEXT,
        FOREIGN KEY (conta_id) REFERENCES contas_pagar (id),
        FOREIGN KEY (parceiro_id) REFERENCES parceiros (id)
    )
    """)
    
    categorias = ["Documentação", "Pequenos Serviços", "Reforma", "Manutenção", "Venda de Materiais"]
    for cat in categorias:
        cursor.execute("INSERT OR IGNORE INTO metas (categoria, meta_valor) VALUES (?, 0.0)", (cat,))
        
    conn.commit()
    conn.close()

# ==========================================
# AUTENTICAÇÃO E LOGIN
# ==========================================
def autenticar_usuario(usuario_input, senha_input):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, usuario, senha_hash, perfil FROM usuarios WHERE usuario = ?", (usuario_input.strip().lower(),))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        user_id, nome, user_login, hash_guardado, perfil = res
        if verificar_senha_hash(senha_input, hash_guardado):
            return {"id": user_id, "nome": nome, "usuario": user_login, "perfil": perfil}
    return None

def tela_login():
    if "usuario_logado" not in st.session_state:
        st.session_state["usuario_logado"] = None

    if st.session_state["usuario_logado"] is None:
        st.title("🔒 Acesso Restrito - Conslin")
        with st.form("form_login"):
            usuario = st.text_input("Usuário").strip().lower()
            senha = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar")
            
            if btn_login:
                dados_user = autenticar_usuario(usuario, senha)
                if dados_user:
                    st.session_state["usuario_logado"] = dados_user
                    st.success(f"Bem-vindo(a), {dados_user['nome']}!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        return False
    return True

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
criar_tabelas()

st.set_page_config(page_title="Sistema de Gestão Conslin", layout="wide")

if tela_login():
    user = st.session_state["usuario_logado"]
    perfil_usuario = user.get("perfil", "Atendente")
    
    st.sidebar.markdown(f"👤 **{user['nome']}**  \n*(Perfil: **{perfil_usuario}**)*")
    if st.sidebar.button("🚪 Sair / Logout"):
        st.session_state["usuario_logado"] = None
        st.rerun()

    CATEGORIAS = ["Documentação", "Pequenos Serviços", "Reforma", "Manutenção", "Venda de Materiais"]
    STATUS_OPCOES = ["Primeiro Contato", "Em Orçamento", "Aprovado / Execução", "Concluído", "Cancelado"]
    TIPOS_PARCEIROS = ["Prestador de Serviço", "Equipe do Escritório", "Fornecedor"]
    TIPOS_CONTAS = ["Dívida", "Acordo", "Prestação de Serviço", "Fornecedor", "Equipe / Salário"]

    st.title("🏗️ Conslin - Gestão Operacional & Financeira")

    menus_por_perfil = {
        "Atendente": [
            "Dashboard & Metas",
            "Cadastro de Clientes",
            "Novo Atendimento / Orçamento",
            "Gestão de Atendimentos"
        ],
        "Admin": [
            "Dashboard & Metas",
            "Cadastro de Clientes",
            "Novo Atendimento / Orçamento",
            "Gestão de Atendimentos",
            "Prestadores & Fornecedores",
            "Contas a Pagar, Dívidas & Acordos",
            "Registrar Pagamentos",
            "Fluxo de Caixa & DRE",
            "⚙️ Gerenciar Usuários"
        ]
    }

    opcoes_menu = menus_por_perfil.get(perfil_usuario, menus_por_perfil["Atendente"])
    menu = st.sidebar.radio("Navegação", opcoes_menu)

    # ----------------------------------------------------
    # DASHBOARD & METAS (DIÁRIA, SEMANAL, MÊS ATUAL E ACUMULADO 12 MESES)
    # ----------------------------------------------------
    if menu == "Dashboard & Metas":
        st.header("🎯 Painel de Metas e Desempenho Temporal")
        
        conn = conectar()
        df_atendimentos = pd.read_sql_query("SELECT * FROM atendimentos", conn)
        df_metas = pd.read_sql_query("SELECT * FROM metas", conn)
        conn.close()

        # Tratamento de datas
        if not df_atendimentos.empty:
            df_atendimentos['data_dt'] = pd.to_datetime(df_atendimentos['data_contato'], errors='coerce').dt.date
            df_aprovados = df_atendimentos[df_atendimentos['status'].isin(["Aprovado / Execução", "Concluído"])].copy()
        else:
            df_aprovados = pd.DataFrame(columns=['categoria', 'valor_fechado', 'data_dt'])

        hoje = date.today()
        inicio_semana = hoje - timedelta(days=hoje.weekday()) # Segunda-feira da semana atual
        inicio_mes = hoje.replace(day=1)
        inicio_ano = hoje.replace(month=1, day=1)

        if perfil_usuario == "Admin":
            with st.expander("⚙️ Ajustar Meta Mensal por Categoria"):
                with st.form("form_metas"):
                    novas_metas = {}
                    for cat in CATEGORIAS:
                        meta_atual = float(df_metas[df_metas['categoria'] == cat]['meta_valor'].values[0]) if not df_metas.empty and cat in df_metas['categoria'].values else 0.0
                        novas_metas[cat] = st.number_input(f"Meta Mensal para {cat} (R$)", value=meta_atual, step=500.0)
                    if st.form_submit_button("Salvar Metas"):
                        conn = conectar()
                        cursor = conn.cursor()
                        for cat, valor in novas_metas.items():
                            cursor.execute("UPDATE metas SET meta_valor = ? WHERE categoria = ?", (valor, cat))
                        conn.commit()
                        conn.close()
                        st.success("Metas atualizadas com sucesso!")
                        st.rerun()

        st.subheader("📊 Resumo Geral de Fechamentos")
        
        # Filtragem por Períodos de Tempo
        val_hoje = df_aprovados[df_aprovados['data_dt'] == hoje]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
        val_semana = df_aprovados[df_aprovados['data_dt'] >= inicio_semana]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
        val_mes = df_aprovados[df_aprovados['data_dt'] >= inicio_mes]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
        val_ano = df_aprovados[df_aprovados['data_dt'] >= inicio_ano]['valor_fechado'].sum() if not df_aprovados.empty else 0.0

        col_d, col_s, col_m, col_a = st.columns(4)
        col_d.metric("Vendas Hoje", f"R$ {val_hoje:,.2f}")
        col_s.metric("Vendas na Semana", f"R$ {val_semana:,.2f}")
        col_m.metric("Vendas no Mês Atual", f"R$ {val_mes:,.2f}")
        col_a.metric("Acumulado do Ano / Periodo", f"R$ {val_ano:,.2f}")

        st.divider()
        st.subheader("🎯 Atingimento da Meta Mensal por Categoria")
        
        cols = st.columns(len(CATEGORIAS))
        for i, cat in enumerate(CATEGORIAS):
            meta_val = float(df_metas[df_metas['categoria'] == cat]['meta_valor'].values[0]) if not df_metas.empty and cat in df_metas['categoria'].values else 0.0
            
            if not df_aprovados.empty:
                realizado_cat = df_aprovados[
                    (df_aprovados['categoria'] == cat) & 
                    (df_aprovados['data_dt'] >= inicio_mes)
                ]['valor_fechado'].sum()
            else:
                realizado_cat = 0.0

            percentual = (realizado_cat / meta_val * 100) if meta_val > 0 else 0.0
            with cols[i]:
                st.metric(label=cat, value=f"R$ {realizado_cat:,.2f}", delta=f"{percentual:.1f}% da meta")
                st.progress(min(percentual / 100, 1.0))

    # ----------------------------------------------------
    # CADASTRO DE CLIENTES
    # ----------------------------------------------------
    elif menu == "Cadastro de Clientes":
        st.header("👤 Cadastro e Seleção de Clientes")
        with st.form("form_cliente"):
            nome = st.text_input("Nome do Cliente / Razão Social *")
            telefone = st.text_input("Telefone / WhatsApp")
            email = st.text_input("E-mail")
            cpf_cnpj = st.text_input("CPF ou CNPJ")
            endereco = st.text_area("Endereço Completo")
            if st.form_submit_button("Cadastrar Cliente"):
                if nome:
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO clientes (nome, telefone, email, cpf_cnpj, endereco) VALUES (?,?,?,?,?)",
                                   (nome, telefone, email, cpf_cnpj, endereco))
                    conn.commit()
                    conn.close()
                    st.success(f"Cliente {nome} cadastrado com sucesso!")
                else:
                    st.error("O campo Nome é obrigatório.")

        st.subheader("Base de Clientes Cadastrados")
        conn = conectar()
        df_clientes = pd.read_sql_query("SELECT * FROM clientes", conn)
        conn.close()
        st.dataframe(df_clientes, use_container_width=True)

    # ----------------------------------------------------
    # NOVO ATENDIMENTO / ORÇAMENTO
    # ----------------------------------------------------
    elif menu == "Novo Atendimento / Orçamento":
        st.header("📝 Registrar Novo Atendimento / Orçamento")
        conn = conectar()
        df_clientes = pd.read_sql_query("SELECT id, nome FROM clientes", conn)
        conn.close()

        if df_clientes.empty:
            st.warning("Nenhum cliente cadastrado. Cadastre um cliente primeiro.")
        else:
            opcoes_clientes = {f"{row['nome']} (ID: {row['id']})": row['id'] for _, row in df_clientes.iterrows()}
            with st.form("form_atendimento"):
                cliente_sel = st.selectbox("Selecione o Cliente", list(opcoes_clientes.keys()))
                categoria = st.selectbox("Categoria do Serviço", CATEGORIAS)
                status = st.selectbox("Status Inicial", STATUS_OPCOES, index=0)
                descricao = st.text_area("Descrição do Serviço / Necessidade")
                valor_orcamento = st.number_input("Valor Estimado / Orçamento (R$)", value=0.0, step=100.0)
                valor_fechado = st.number_input("Valor Fechado / Venda (R$)", value=0.0, step=100.0)
                despesas = st.number_input("Despesas Previstas (R$)", value=0.0, step=50.0)
                data_contato = st.date_input("Data do Fechamento / Contato", value=date.today())
                if st.form_submit_button("Salvar Atendimento"):
                    cliente_id = opcoes_clientes[cliente_sel]
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, data_contato)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, str(data_contato)))
                    conn.commit()
                    conn.close()
                    st.success("Atendimento registrado no banco de dados!")

    # ----------------------------------------------------
    # GESTÃO DE ATENDIMENTOS (COM EXPORTAÇÃO PDF)
    # ----------------------------------------------------
    elif menu == "Gestão de Atendimentos":
        st.header("📋 Gestão e Atualização do Funil de Atendimentos")
        conn = conectar()
        query = """
        SELECT a.id, c.nome as Cliente, a.categoria as Categoria, a.status as Status, 
               a.valor_orcamento as [Orçado (R$)], a.valor_fechado as [Fechado (R$)], 
               a.despesas as [Despesas (R$)], a.descricao as Descrição, a.data_contato as Data
        FROM atendimentos a
        LEFT JOIN clientes c ON a.cliente_id = c.id
        """
        df_atendimentos = pd.read_sql_query(query, conn)
        conn.close()

        if df_atendimentos.empty:
            st.info("Nenhum atendimento registrado até o momento.")
        else:
            st.dataframe(df_atendimentos, use_container_width=True)

            pdf_bytes = gerar_pdf_tabela("Relatorio de Atendimentos - Conslin", df_atendimentos[['id', 'Cliente', 'Categoria', 'Status', 'Fechado (R$)']])
            st.download_button("📄 Gerar PDF de Todos os Atendimentos", data=pdf_bytes, file_name="atendimentos_conslin.pdf", mime="application/pdf")

            st.divider()
            st.subheader("✏️ Edição & Exportação de PDF Individual")
            atendimento_id = st.number_input("Informe o ID do Atendimento", min_value=1, step=1)
            registro = df_atendimentos[df_atendimentos['id'] == atendimento_id]
            
            if not registro.empty:
                reg = registro.iloc[0]
                st.write(f"Editando atendimento do cliente: **{reg['Cliente']}**")
                
                pdf_ind = gerar_pdf_atendimento(reg['Cliente'], reg['Categoria'], reg['Status'], float(reg['Orçado (R$)']), float(reg['Fechado (R$)']), reg['Descrição'])
                st.download_button(f"📥 Baixar Orçamento/PDF (ID #{reg['id']})", data=pdf_ind, file_name=f"orcamento_atendimento_{reg['id']}.pdf", mime="application/pdf")

                with st.form("form_edicao"):
                    novo_status = st.selectbox("Novo Status", STATUS_OPCOES, index=STATUS_OPCOES.index(reg['Status']))
                    novo_orcamento = st.number_input("Novo Valor Orçado (R$)", value=float(reg['Orçado (R$)']))
                    novo_fechado = st.number_input("Novo Valor Fechado (R$)", value=float(reg['Fechado (R$)']))
                    novas_despesas = st.number_input("Novas Despesas (R$)", value=float(reg['Despesas (R$)']))
                    if st.form_submit_button("Atualizar Atendimento"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        UPDATE atendimentos 
                        SET status = ?, valor_orcamento = ?, valor_fechado = ?, despesas = ?
                        WHERE id = ?
                        """, (novo_status, novo_orcamento, novo_fechado, novas_despesas, atendimento_id))
                        conn.commit()
                        conn.close()
                        st.success("Registro atualizado com sucesso!")
                        st.rerun()

    # ----------------------------------------------------
    # PRESTADORES, EQUIPE E FORNECEDORES (ADMIN)
    # ----------------------------------------------------
    elif menu == "Prestadores & Fornecedores":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("👷 Cadastrar Prestadores, Equipe e Fornecedores")
            with st.form("form_parceiro"):
                nome = st.text_input("Nome / Razão Social *")
                tipo = st.selectbox("Tipo de Cadastro", TIPOS_PARCEIROS)
                telefone = st.text_input("Telefone / WhatsApp")
                cpf_cnpj = st.text_input("CPF ou CNPJ")
                chave_pix = st.text_input("Chave PIX / Dados Bancários")
                observacao = st.text_area("Observações (Especialidade, Condições, etc.)")
                if st.form_submit_button("Cadastrar"):
                    if nome:
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        INSERT INTO parceiros (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao))
                        conn.commit()
                        conn.close()
                        st.success(f"{tipo} '{nome}' cadastrado com sucesso!")
                    else:
                        st.error("O campo Nome é obrigatório.")

            st.subheader("Lista de Prestadores, Equipe e Fornecedores")
            conn = conectar()
            df_parceiros = pd.read_sql_query("SELECT * FROM parceiros", conn)
            conn.close()
            st.dataframe(df_parceiros, use_container_width=True)

    # ----------------------------------------------------
    # CONTAS A PAGAR (ADMIN)
    # ----------------------------------------------------
    elif menu == "Contas a Pagar, Dívidas & Acordos":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("💸 Contas a Pagar, Dívidas e Acordos")
            conn = conectar()
            df_parceiros = pd.read_sql_query("SELECT id, nome, tipo FROM parceiros", conn)
            conn.close()

            if df_parceiros.empty:
                st.warning("Cadastre primeiro um Prestador, Integrante da Equipe ou Fornecedor.")
            else:
                opcoes_parceiros = {f"{row['nome']} ({row['tipo']} - ID: {row['id']})": row['id'] for _, row in df_parceiros.iterrows()}
                
                with st.form("form_contas"):
                    parceiro_sel = st.selectbox("Selecione o Beneficiário / Credor", list(opcoes_parceiros.keys()))
                    tipo_conta = st.selectbox("Tipo de Lançamento", TIPOS_CONTAS)
                    descricao = st.text_input("Descrição (ex: Material de Construção, Mão de Obra, Parcela Acordo #1)")
                    valor = st.number_input("Valor (R$)", min_value=0.01, step=50.0)
                    data_vencimento = st.date_input("Data de Vencimento")
                    status = st.selectbox("Status", ["Pendente", "Acordado / Parcelado", "Pago"])
                    
                    if st.form_submit_button("Lançar Conta"):
                        parceiro_id = opcoes_parceiros[parceiro_sel]
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        INSERT INTO contas_pagar (parceiro_id, descricao, tipo_conta, valor, data_vencimento, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (parceiro_id, descricao, tipo_conta, valor, str(data_vencimento), status))
                        conn.commit()
                        conn.close()
                        st.success("Lançamento registrado com sucesso!")

            st.subheader("📋 Relação de Contas a Pagar e Dívidas")
            conn = conectar()
            query = """
            SELECT cp.id, p.nome as Credor, cp.tipo_conta as Tipo, cp.descricao as Descrição, 
                   cp.valor as [Valor (R$)], cp.data_vencimento as Vencimento, cp.status as Status
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
            """
            df_contas = pd.read_sql_query(query, conn)
            conn.close()

            if not df_contas.empty:
                st.dataframe(df_contas, use_container_width=True)
                pendentes = df_contas[df_contas['Status'] != 'Pago']['Valor (R$)'].sum()
                st.warning(f"⚠️ Total Pendente / Em Aberto em Dívidas e Contas: **R$ {pendentes:,.2f}**")
                
                pdf_contas = gerar_pdf_tabela("Relatorio de Contas a Pagar - Conslin", df_contas[['Credor', 'Tipo', 'Valor (R$)', 'Vencimento', 'Status']])
                st.download_button("📄 Baixar Relatório de Contas (PDF)", data=pdf_contas, file_name="contas_a_pagar.pdf", mime="application/pdf")

    # ----------------------------------------------------
    # REGISTRAR PAGAMENTOS (ADMIN)
    # ----------------------------------------------------
    elif menu == "Registrar Pagamentos":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("💳 Registrar Pagamento Efetuado")
            conn = conectar()
            query = """
            SELECT cp.id, p.nome as Credor, cp.descricao, cp.valor, cp.data_vencimento, cp.parceiro_id
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
            WHERE cp.status != 'Pago'
            """
            df_pendentes = pd.read_sql_query(query, conn)
            conn.close()

            if df_pendentes.empty:
                st.info("Não há contas pendentes para pagamento no momento.")
            else:
                opcoes_contas = {
                    f"ID {row['id']} - {row['Credor']} - {row['descricao']} - R$ {row['valor']:,.2f} (Venc: {row['data_vencimento']})": row
                    for _, row in df_pendentes.iterrows()
                }
                conta_sel = st.selectbox("Selecione a Conta / Dívida a ser Paga", list(opcoes_contas.keys()))
                dados_conta = opcoes_contas[conta_sel]

                with st.form("form_pagamento"):
                    valor_pago = st.number_input("Valor Pago (R$)", value=float(dados_conta['valor']), step=10.0)
                    forma_pagamento = st.selectbox("Forma de Pagamento", ["PIX", "Transferência Bancária", "Dinheiro", "Boleto", "Cartão"])
                    comprovante = st.text_input("Referência / N° Comprovante / Obs")
                    data_pagamento = st.date_input("Data do Pagamento")

                    if st.form_submit_button("Confirmar Pagamento"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        INSERT INTO pagamentos (conta_id, parceiro_id, valor_pago, data_pagamento, forma_pagamento, comprovante_ref)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (dados_conta['id'], dados_conta['parceiro_id'], valor_pago, str(data_pagamento), forma_pagamento, comprovante))
                        
                        if valor_pago >= dados_conta['valor']:
                            cursor.execute("UPDATE contas_pagar SET status = 'Pago' WHERE id = ?", (dados_conta['id'],))
                        else:
                            novo_valor = dados_conta['valor'] - valor_pago
                            cursor.execute("UPDATE contas_pagar SET valor = ? WHERE id = ?", (novo_valor, dados_conta['id']))

                        conn.commit()
                        conn.close()
                        st.success("Pagamento registrado com sucesso!")
                        st.rerun()

            st.subheader("📜 Histórico de Pagamentos Realizados")
            conn = conectar()
            query_hist = """
            SELECT pg.id, p.nome as Beneficiário, pg.valor_pago as [Valor Pago (R$)], 
                   pg.data_pagamento as Data, pg.forma_pagamento as Forma, pg.comprovante_ref as Observação
            FROM pagamentos pg
            LEFT JOIN parceiros p ON pg.parceiro_id = p.id
            """
            df_hist = pd.read_sql_query(query_hist, conn)
            conn.close()
            st.dataframe(df_hist, use_container_width=True)

    # ----------------------------------------------------
    # FLUXO DE CAIXA & DRE (ADMIN)
    # ----------------------------------------------------
    elif menu == "Fluxo de Caixa & DRE":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("💰 Resumo de Entradas, Saídas e Lucratividade")
            conn = conectar()
            df_atendimentos = pd.read_sql_query("SELECT SUM(valor_fechado) as entradas FROM atendimentos WHERE status IN ('Aprovado / Execução', 'Concluído')", conn)
            df_saidas = pd.read_sql_query("SELECT SUM(valor_pago) as pagamentos_efetuados FROM pagamentos", conn)
            df_pendentes = pd.read_sql_query("SELECT SUM(valor) as pendencias FROM contas_pagar WHERE status != 'Pago'", conn)
            conn.close()

            total_entradas = df_atendimentos['entradas'].values[0] if df_atendimentos['entradas'].values[0] else 0.0
            total_pagos = df_saidas['pagamentos_efetuados'].values[0] if df_saidas['pagamentos_efetuados'].values[0] else 0.0
            total_pendencias = df_pendentes['pendencias'].values[0] if df_pendentes['pendencias'].values[0] else 0.0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Entradas (Vendas)", f"R$ {total_entradas:,.2f}")
            col2.metric("Total Saídas (Pagas)", f"R$ {total_pagos:,.2f}")
            col3.metric("Contas a Pagar (Aberto)", f"R$ {total_pendencias:,.2f}")
            col4.metric("Saldo do Exercício", f"R$ {(total_entradas - total_pagos):,.2f}")

    # ----------------------------------------------------
    # GERENCIAR USUÁRIOS E SENHAS
    # ----------------------------------------------------
    elif menu == "⚙️ Gerenciar Usuários":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("⚙️ Gestão de Usuários e Permissões")
            
            tab_cadastrar, tab_listar, tab_alterar_perfil, tab_minha_senha = st.tabs([
                "➕ Novo Usuário", 
                "👥 Usuários Cadastrados", 
                "🛠️ Alterar Perfil de Acesso",
                "🔑 Alterar Minha Senha"
            ])

            with tab_cadastrar:
                with st.form("form_novo_usuario"):
                    st.subheader("Cadastrar Novo Acesso")
                    nome_novo = st.text_input("Nome Completo / Pessoa")
                    login_novo = st.text_input("Nome de Usuário (login)").strip().lower()
                    senha_nova = st.text_input("Senha", type="password")
                    perfil_novo = st.selectbox("Perfil de Acesso", ["Atendente", "Admin"])
                    
                    if st.form_submit_button("Cadastrar Usuário"):
                        if nome_novo and login_novo and senha_nova:
                            conn = conectar()
                            cursor = conn.cursor()
                            try:
                                cursor.execute("""
                                INSERT INTO usuarios (nome, usuario, senha_hash, perfil)
                                VALUES (?, ?, ?, ?)
                                """, (nome_novo, login_novo, gerar_hash_senha(senha_nova), perfil_novo))
                                conn.commit()
                                st.success(f"Usuário **{login_novo}** cadastrado como **{perfil_novo}**!")
                            except sqlite3.IntegrityError:
                                st.error("Este nome de usuário já existe. Escolha outro.")
                            finally:
                                conn.close()
                        else:
                            st.error("Preencha todos os campos obrigatórios.")

            with tab_listar:
                st.subheader("Lista de Acessos ao Sistema")
                conn = conectar()
                df_users = pd.read_sql_query("SELECT id, nome, usuario, perfil FROM usuarios", conn)
                conn.close()
                st.dataframe(df_users, use_container_width=True)

            with tab_alterar_perfil:
                st.subheader("Alterar Permissões de Usuários Existentes")
                conn = conectar()
                df_users = pd.read_sql_query("SELECT id, usuario, perfil FROM usuarios", conn)
                conn.close()

                if not df_users.empty:
                    mapa_usuarios = {f"{row['usuario']} (Atual: {row['perfil']})": (row['id'], row['perfil']) for _, row in df_users.iterrows()}
                    user_selecionado = st.selectbox("Selecione o Usuário", list(mapa_usuarios.keys()))
                    user_id, perfil_atual = mapa_usuarios[user_selecionado]

                    with st.form("form_mudar_perfil"):
                        novo_perfil = st.selectbox("Novo Perfil", ["Atendente", "Admin"], index=0 if perfil_atual == "Atendente" else 1)
                        if st.form_submit_button("Atualizar Perfil"):
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE usuarios SET perfil = ? WHERE id = ?", (novo_perfil, user_id))
                            conn.commit()
                            conn.close()
                            st.success("Perfil atualizado com sucesso!")
                            st.rerun()

            with tab_minha_senha:
                st.subheader("Alterar Minha Senha de Acesso")
                with st.form("form_alterar_senha"):
                    senha_atual = st.text_input("Senha Atual", type="password")
                    nova_senha = st.text_input("Nova Senha", type="password")
                    confirma_senha = st.text_input("Confirmar Nova Senha", type="password")
                    
                    if st.form_submit_button("Atualizar Senha"):
                        if nova_senha != confirma_senha:
                            st.error("A nova senha e a confirmação não coincidem.")
                        elif len(nova_senha) < 4:
                            st.error("A nova senha deve ter pelo menos 4 caracteres.")
                        else:
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (user['id'],))
                            hash_atual = cursor.fetchone()[0]
                            
                            if verificar_senha_hash(senha_atual, hash_atual):
                                nova_hash = gerar_hash_senha(nova_senha)
                                cursor.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (nova_hash, user['id']))
                                conn.commit()
                                conn.close()
                                st.success("Sua senha foi alterada com sucesso!")
                            else:
                                conn.close()
                                st.error("Sua senha atual está incorreta.")
