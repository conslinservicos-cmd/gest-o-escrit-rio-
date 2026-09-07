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
        meta_diaria REAL DEFAULT 0.0,
        meta_semanal REAL DEFAULT 0.0,
        meta_valor REAL DEFAULT 0.0
    )
    """)
    
    # Migração de colunas de metas
    cursor.execute("PRAGMA table_info(metas)")
    colunas_metas = [col[1] for col in cursor.fetchall()]
    if "meta_diaria" not in colunas_metas:
        cursor.execute("ALTER TABLE metas ADD COLUMN meta_diaria REAL DEFAULT 0.0")
    if "meta_semanal" not in colunas_metas:
        cursor.execute("ALTER TABLE metas ADD COLUMN meta_semanal REAL DEFAULT 0.0")

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

    # Nova Tabela: Contas / Parcelas a Receber
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contas_receber (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        atendimento_id INTEGER,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        data_vencimento DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pendente',
        FOREIGN KEY (cliente_id) REFERENCES clientes (id),
        FOREIGN KEY (atendimento_id) REFERENCES atendimentos (id)
    )
    """)
    
    categorias = ["Documentação", "Pequenos Serviços", "Reforma", "Manutenção", "Venda de Materiais"]
    for cat in categorias:
        cursor.execute("INSERT OR IGNORE INTO metas (categoria, meta_diaria, meta_semanal, meta_valor) VALUES (?, 0.0, 0.0, 0.0)", (cat,))
        
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
            "Gestão de Atendimentos",
            "Contas e Parcelas a Receber"
        ],
        "Admin": [
            "Dashboard & Metas",
            "Cadastro de Clientes",
            "Novo Atendimento / Orçamento",
            "Gestão de Atendimentos",
            "Contas e Parcelas a Receber",
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
    # DASHBOARD & METAS
    # ----------------------------------------------------
    if menu == "Dashboard & Metas":
        st.header("🎯 Painel de Metas e Desempenho Temporal")
        
        conn = conectar()
        df_atendimentos = pd.read_sql_query("SELECT * FROM atendimentos", conn)
        df_metas = pd.read_sql_query("SELECT * FROM metas", conn)
        conn.close()

        if not df_atendimentos.empty:
            df_atendimentos['data_dt'] = pd.to_datetime(df_atendimentos['data_contato'], errors='coerce').dt.date
            df_aprovados = df_atendimentos[df_atendimentos['status'].isin(["Aprovado / Execução", "Concluído"])].copy()
        else:
            df_aprovados = pd.DataFrame(columns=['categoria', 'valor_fechado', 'data_dt'])

        hoje = date.today()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        inicio_mes = hoje.replace(day=1)
        inicio_ano = hoje.replace(month=1, day=1)

        if perfil_usuario == "Admin":
            with st.expander("⚙️ Configurar e Editar Metas (Diária, Semanal e Mensal) por Categoria"):
                st.write("Digite manualmente os valores de meta para cada categoria. Se a meta diária ou semanal ainda não tiver sido salva, o sistema trará uma sugestão inicial (semanal = mensal ÷ 4,33 | diária = mensal ÷ 22 dias úteis de seg. a sex.).")
                
                with st.form("form_metas_completas"):
                    novas_metas_diarias = {}
                    novas_metas_semanais = {}
                    novas_metas_mensais = {}
                    
                    for cat in CATEGORIAS:
                        st.markdown(f"**📍 Categoria: {cat}**")
                        row_cat = df_metas[df_metas['categoria'] == cat] if not df_metas.empty and cat in df_metas['categoria'].values else pd.DataFrame()
                        
                        m_mensal_cad = float(row_cat['meta_valor'].values[0]) if not row_cat.empty and 'meta_valor' in row_cat.columns else 0.0
                        m_semanal_cad = float(row_cat['meta_semanal'].values[0]) if not row_cat.empty and 'meta_semanal' in row_cat.columns else 0.0
                        m_diaria_cad = float(row_cat['meta_diaria'].values[0]) if not row_cat.empty and 'meta_diaria' in row_cat.columns else 0.0
                        
                        sugestao_semanal = round(m_mensal_cad / 4.33, 2) if m_mensal_cad > 0 else 0.0
                        sugestao_diaria = round(m_mensal_cad / 22.0, 2) if m_mensal_cad > 0 else 0.0

                        c1, c2, c3 = st.columns(3)
                        val_m = c1.number_input(f"Meta Mensal ({cat})", value=m_mensal_cad, step=500.0, key=f"m_{cat}")
                        
                        val_s_default = m_semanal_cad if m_semanal_cad > 0 else sugestao_semanal
                        val_d_default = m_diaria_cad if m_diaria_cad > 0 else sugestao_diaria
                        
                        val_s = c2.number_input(f"Meta Semanal ({cat})", value=val_s_default, step=100.0, key=f"s_{cat}", help="Livre para edição manual")
                        val_d = c3.number_input(f"Meta Diária ({cat})", value=val_d_default, step=50.0, key=f"d_{cat}", help="Livre para edição manual (segunda a sexta)")
                        
                        novas_metas_mensais[cat] = val_m
                        novas_metas_semanais[cat] = val_s
                        novas_metas_diarias[cat] = val_d
                        st.divider()

                    if st.form_submit_button("💾 Salvar Todas as Metas"):
                        conn = conectar()
                        cursor = conn.cursor()
                        for cat in CATEGORIAS:
                            cursor.execute("""
                            UPDATE metas 
                            SET meta_diaria = ?, meta_semanal = ?, meta_valor = ? 
                            WHERE categoria = ?
                            """, (novas_metas_diarias[cat], novas_metas_semanais[cat], novas_metas_mensais[cat], cat))
                        conn.commit()
                        conn.close()
                        st.success("Metas salvas e atualizadas com sucesso!")
                        st.rerun()

        st.subheader("📊 Resumo Geral de Fechamentos x Metas Totais")
        
        val_hoje = df_aprovados[df_aprovados['data_dt'] == hoje]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
        val_semana = df_aprovados[df_aprovados['data_dt'] >= inicio_semana]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
        val_mes = df_aprovados[df_aprovados['data_dt'] >= inicio_mes]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
        val_ano = df_aprovados[df_aprovados['data_dt'] >= inicio_ano]['valor_fechado'].sum() if not df_aprovados.empty else 0.0

        meta_total_diaria = df_metas['meta_diaria'].sum() if not df_metas.empty and 'meta_diaria' in df_metas.columns else 0.0
        meta_total_semanal = df_metas['meta_semanal'].sum() if not df_metas.empty and 'meta_semanal' in df_metas.columns else 0.0
        meta_total_mensal = df_metas['meta_valor'].sum() if not df_metas.empty else 0.0

        col_d, col_s, col_m, col_a = st.columns(4)
        col_d.metric("Vendas Hoje", f"R$ {val_hoje:,.2f}", delta=f"{((val_hoje/meta_total_diaria)*100 if meta_total_diaria > 0 else 0):.1f}% da meta" if meta_total_diaria > 0 else "Sem meta definida")
        col_s.metric("Vendas na Semana", f"R$ {val_semana:,.2f}", delta=f"{((val_semana/meta_total_semanal)*100 if meta_total_semanal > 0 else 0):.1f}% da meta" if meta_total_semanal > 0 else "Sem meta definida")
        col_m.metric("Vendas no Mês Atual", f"R$ {val_mes:,.2f}", delta=f"{((val_mes/meta_total_mensal)*100 if meta_total_mensal > 0 else 0):.1f}% da meta" if meta_total_mensal > 0 else "Sem meta definida")
        col_a.metric("Acumulado do Ano", f"R$ {val_ano:,.2f}")

        st.divider()
        st.subheader("🎯 Atingimento de Metas por Categoria")
        
        visao_periodo = st.radio("Selecione a meta que deseja comparar:", ["Meta Diária (Hoje)", "Meta Semanal (Semana Atual)", "Meta Mensal (Mês Vigente)"], horizontal=True)

        cols = st.columns(len(CATEGORIAS))
        for i, cat in enumerate(CATEGORIAS):
            row_cat = df_metas[df_metas['categoria'] == cat] if not df_metas.empty and cat in df_metas['categoria'].values else pd.DataFrame()
            
            if visao_periodo == "Meta Diária (Hoje)":
                meta_val = float(row_cat['meta_diaria'].values[0]) if not row_cat.empty and 'meta_diaria' in row_cat.columns else 0.0
                realizado_cat = df_aprovados[(df_aprovados['categoria'] == cat) & (df_aprovados['data_dt'] == hoje)]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
            elif visao_periodo == "Meta Semanal (Semana Atual)":
                meta_val = float(row_cat['meta_semanal'].values[0]) if not row_cat.empty and 'meta_semanal' in row_cat.columns else 0.0
                realizado_cat = df_aprovados[(df_aprovados['categoria'] == cat) & (df_aprovados['data_dt'] >= inicio_semana)]['valor_fechado'].sum() if not df_aprovados.empty else 0.0
            else:
                meta_val = float(row_cat['meta_valor'].values[0]) if not row_cat.empty else 0.0
                realizado_cat = df_aprovados[(df_aprovados['categoria'] == cat) & (df_aprovados['data_dt'] >= inicio_mes)]['valor_fechado'].sum() if not df_aprovados.empty else 0.0

            percentual = (realizado_cat / meta_val * 100) if meta_val > 0 else 0.0
            with cols[i]:
                st.markdown(f"**{cat}**")
                st.metric(label="Realizado", value=f"R$ {realizado_cat:,.2f}", delta=f"{percentual:.1f}% de R$ {meta_val:,.2f}")
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
                
                gerar_recebivel = st.checkbox("Gerar automaticamente lançamento de Conta a Receber (vencimento hoje)", value=True)

                if st.form_submit_button("Salvar Atendimento"):
                    cliente_id = opcoes_clientes[cliente_sel]
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, data_contato)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, str(data_contato)))
                    
                    atendimento_id = cursor.lastrowid

                    if gerar_recebivel and status in ["Aprovado / Execução", "Concluído"] and valor_fechado > 0:
                        cursor.execute("""
                        INSERT INTO contas_receber (cliente_id, atendimento_id, descricao, valor, data_vencimento, status)
                        VALUES (?, ?, ?, ?, ?, 'Pendente')
                        """, (cliente_id, atendimento_id, f"Fechamento - {categoria}", valor_fechado, str(data_contato)))

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
        SELECT a.id, c.nome as Cliente, a.cliente_id, a.categoria as Categoria, a.status as Status, 
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
            st.dataframe(df_atendimentos[['id', 'Cliente', 'Categoria', 'Status', 'Orçado (R$)', 'Fechado (R$)', 'Data']], use_container_width=True)

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
                    gerar_receber_edicao = st.checkbox("Lançar novo valor em Contas a Receber se aprovado/fechado", value=False)
                    
                    if st.form_submit_button("Atualizar Atendimento"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        UPDATE atendimentos 
                        SET status = ?, valor_orcamento = ?, valor_fechado = ?, despesas = ?
                        WHERE id = ?
                        """, (novo_status, novo_orcamento, novo_fechado, novas_despesas, atendimento_id))

                        if gerar_receber_edicao and novo_status in ["Aprovado / Execução", "Concluído"] and novo_fechado > 0:
                            cursor.execute("""
                            INSERT INTO contas_receber (cliente_id, atendimento_id, descricao, valor, data_vencimento, status)
                            VALUES (?, ?, ?, ?, ?, 'Pendente')
                            """, (int(reg['cliente_id']), atendimento_id, f"Ajuste Fechamento - {reg['Categoria']}", novo_fechado, str(date.today())))

                        conn.commit()
                        conn.close()
                        st.success("Registro atualizado com sucesso!")
                        st.rerun()

    # ----------------------------------------------------
    # CONTAS E PARCELAS A RECEBER
    # ----------------------------------------------------
    elif menu == "Contas e Parcelas a Receber":
        st.header("💵 Lançamento e Controle de Contas a Receber")
        
        conn = conectar()
        df_clientes = pd.read_sql_query("SELECT id, nome FROM clientes", conn)
        conn.close()

        if df_clientes.empty:
            st.warning("Cadastre primeiro um cliente para registrar contas a receber.")
        else:
            opcoes_clientes = {f"{row['nome']} (ID: {row['id']})": row['id'] for _, row in df_clientes.iterrows()}

            with st.expander("➕ Lançar Nova Conta ou Parcela a Receber"):
                with st.form("form_contas_receber"):
                    cliente_sel = st.selectbox("Selecione o Cliente", list(opcoes_clientes.keys()))
                    descricao = st.text_input("Descrição (ex: Parcela 1/3 Reforma, Medição de Serviços, Honorários)")
                    valor = st.number_input("Valor a Receber (R$)", min_value=0.01, step=100.0)
                    data_vencimento = st.date_input("Data de Vencimento Prevista", value=date.today())
                    status_rec = st.selectbox("Status", ["Pendente", "Recebido"])

                    if st.form_submit_button("Lançar Valor a Receber"):
                        cliente_id = opcoes_clientes[cliente_sel]
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        INSERT INTO contas_receber (cliente_id, descricao, valor, data_vencimento, status)
                        VALUES (?, ?, ?, ?, ?)
                        """, (cliente_id, descricao, valor, str(data_vencimento), status_rec))
                        conn.commit()
                        conn.close()
                        st.success("Previsão de recebimento gravada com sucesso!")
                        st.rerun()

            st.subheader("📋 Lista de Recebimentos Previstos e Efetuados")
            conn = conectar()
            query_rec = """
            SELECT cr.id, c.nome as Cliente, cr.descricao as Descrição, cr.valor as [Valor (R$)], 
                   cr.data_vencimento as [Vencimento], cr.status as Status
            FROM contas_receber cr
            LEFT JOIN clientes c ON cr.cliente_id = c.id
            ORDER BY cr.data_vencimento ASC
            """
            df_rec = pd.read_sql_query(query_rec, conn)
            conn.close()

            if not df_rec.empty:
                st.dataframe(df_rec, use_container_width=True)
                
                st.divider()
                st.subheader("✅ Confirmar Recebimento / Dar Baixa")
                df_pendentes_rec = df_rec[df_rec['Status'] == 'Pendente']
                
                if not df_pendentes_rec.empty:
                    rec_id_sel = st.selectbox("Selecione o ID do lançamento para marcar como RECEBIDO:", df_pendentes_rec['id'].tolist())
                    if st.button("Marcar como Recebido"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE contas_receber SET status = 'Recebido' WHERE id = ?", (rec_id_sel,))
                        conn.commit()
                        conn.close()
                        st.success(f"Recebimento ID #{rec_id_sel} confirmado!")
                        st.rerun()
                else:
                    st.info("Todas as contas a receber listadas já estão com status 'Recebido'.")

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
    # CONTAS A PAGAR, DÍVIDAS E ACORDOS (ADMIN)
    # ----------------------------------------------------
    elif menu == "Contas a Pagar, Dívidas & Acordos":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("💸 Contas a Pagar, Dívidas e Acordos")
            conn = conectar()
            df_parceiros = pd.read_sql_query("SELECT id, nome FROM parceiros", conn)
            conn.close()

            opcoes_parceiros = {f"{row['nome']} (ID: {row['id']})": row['id'] for _, row in df_parceiros.iterrows()}
            opcoes_parceiros["Nenhum / Não vinculado"] = None

            with st.expander("➕ Nova Conta / Dívida / Acordo a Pagar"):
                with st.form("form_contas_pagar"):
                    parceiro_sel = st.selectbox("Vincular a Parceiro/Fornecedor (Opcional)", list(opcoes_parceiros.keys()))
                    descricao = st.text_input("Descrição do Débito / Conta *")
                    tipo_conta = st.selectbox("Tipo de Conta", TIPOS_CONTAS)
                    valor = st.number_input("Valor a Pagar (R$)", min_value=0.01, step=50.0)
                    data_vencimento = st.date_input("Data de Vencimento", value=date.today())
                    status_p = st.selectbox("Status", ["Pendente", "Pago", "Acordo / Parcelado"])

                    if st.form_submit_button("Salvar Conta a Pagar"):
                        if descricao:
                            parceiro_id = opcoes_parceiros[parceiro_sel]
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("""
                            INSERT INTO contas_pagar (parceiro_id, descricao, tipo_conta, valor, data_vencimento, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """, (parceiro_id, descricao, tipo_conta, valor, str(data_vencimento), status_p))
                            conn.commit()
                            conn.close()
                            st.success("Conta a pagar inserida com sucesso!")
                            st.rerun()
                        else:
                            st.error("Informe uma descrição.")

            st.subheader("📋 Painel Geral de Dívidas e Obrigações")
            conn = conectar()
            query_pagar = """
            SELECT cp.id, p.nome as Parceiro, cp.descricao as Descrição, cp.tipo_conta as [Tipo], 
                   cp.valor as [Valor (R$)], cp.data_vencimento as [Vencimento], cp.status as Status
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
            ORDER BY cp.data_vencimento ASC
            """
            df_pagar = pd.read_sql_query(query_pagar, conn)
            conn.close()
            st.dataframe(df_pagar, use_container_width=True)

    # ----------------------------------------------------
    # REGISTRAR PAGAMENTOS (ADMIN)
    # ----------------------------------------------------
    elif menu == "Registrar Pagamentos":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("💳 Registrar Pagamento Efetuado")
            conn = conectar()
            df_pendentes = pd.read_sql_query("""
            SELECT cp.id, cp.descricao, cp.valor, p.nome as parceiro_nome, cp.parceiro_id 
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
            WHERE cp.status != 'Pago'
            """, conn)
            conn.close()

            if df_pendentes.empty:
                st.info("Não há contas pendentes para baixa no momento.")
            else:
                opcoes_contas = {f"ID: {row['id']} - {row['descricao']} (R$ {row['valor']:,.2f})": row['id'] for _, row in df_pendentes.iterrows()}
                
                with st.form("form_pagamento"):
                    conta_sel = st.selectbox("Selecione a Conta Pagar", list(opcoes_contas.keys()))
                    valor_pago = st.number_input("Valor Pago (R$)", min_value=0.01, step=50.0)
                    data_pagamento = st.date_input("Data do Pagamento", value=date.today())
                    forma_pagamento = st.selectbox("Forma de Pagamento", ["PIX", "Transferência / TED", "Dinheiro", "Boleto", "Cartão"])
                    comprovante_ref = st.text_input("Código de Autenticação / Ref. Comprovante (Opcional)")

                    if st.form_submit_button("Confirmar Pagamento"):
                        conta_id = opcoes_contas[conta_sel]
                        reg_c = df_pendentes[df_pendentes['id'] == conta_id].iloc[0]
                        parceiro_id = reg_c['parceiro_id']

                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("""
                        INSERT INTO pagamentos (conta_id, parceiro_id, valor_pago, data_pagamento, forma_pagamento, comprovante_ref)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (conta_id, parceiro_id, valor_pago, str(data_pagamento), forma_pagamento, comprovante_ref))
                        
                        cursor.execute("UPDATE contas_pagar SET status = 'Pago' WHERE id = ?", (conta_id,))
                        conn.commit()
                        conn.close()
                        st.success("Pagamento baixado e registrado com sucesso!")
                        st.rerun()

    # ----------------------------------------------------
    # FLUXO DE CAIXA & DRE (ADMIN)
    # ----------------------------------------------------
    elif menu == "Fluxo de Caixa & DRE":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("📈 Fluxo de Caixa e DRE Gerencial")
            
            conn = conectar()
            df_rec = pd.read_sql_query("SELECT valor, status, data_vencimento FROM contas_receber WHERE status = 'Recebido'", conn)
            df_pag = pd.read_sql_query("SELECT valor_pago as valor, data_pagamento FROM pagamentos", conn)
            conn.close()

            total_recebido = df_rec['valor'].sum() if not df_rec.empty else 0.0
            total_pago = df_pag['valor'].sum() if not df_pag.empty else 0.0
            saldo_caixa = total_recebido - total_pago

            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Entradas (Recebimentos)", f"R$ {total_recebido:,.2f}")
            col2.metric("Total de Saídas (Pagamentos)", f"R$ {total_pago:,.2f}")
            col3.metric("Saldo Operacional", f"R$ {saldo_caixa:,.2f}")

    # ----------------------------------------------------
    # GERENCIAR USUÁRIOS (ADMIN)
    # ----------------------------------------------------
    elif menu == "⚙️ Gerenciar Usuários":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso não autorizado para o seu perfil.")
        else:
            st.header("⚙️ Gestão de Usuários do Sistema")
            
            with st.expander("➕ Cadastrar Novo Usuário"):
                with st.form("form_novo_usuario"):
                    novo_nome = st.text_input("Nome Completo *")
                    novo_login = st.text_input("Login de Acesso *").strip().lower()
                    nova_senha = st.text_input("Senha *", type="password")
                    novo_perfil = st.selectbox("Perfil de Acesso", ["Atendente", "Admin"])

                    if st.form_submit_button("Salvar Usuário"):
                        if novo_nome and novo_login and nova_senha:
                            hash_s = gerar_hash_senha(nova_senha)
                            conn = conectar()
                            cursor = conn.cursor()
                            try:
                                cursor.execute("""
                                INSERT INTO usuarios (nome, usuario, senha_hash, perfil)
                                VALUES (?, ?, ?, ?)
                                """, (novo_nome, novo_login, hash_s, novo_perfil))
                                conn.commit()
                                st.success(f"Usuário {novo_login} cadastrado com sucesso!")
                            except sqlite3.IntegrityError:
                                st.error("Nome de usuário (login) já existe. Escolha outro.")
                            finally:
                                conn.close()
                        else:
                            st.error("Preencha todos os campos obrigatórios.")

            st.subheader("Usuários Ativos")
            conn = conectar()
            df_users = pd.read_sql_query("SELECT id, nome, usuario, perfil FROM usuarios", conn)
            conn.close()
            st.dataframe(df_users, use_container_width=True)
