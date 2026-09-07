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
# CRIPTOGRAFIA E BANCO DE DADOS
# ==========================================
def gerar_hash_senha(senha):
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def verificar_senha_hash(senha_digitada, hash_guardado):
    return gerar_hash_senha(senha_digitada) == hash_guardado

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
        cursor.execute("INSERT INTO usuarios (nome, usuario, senha_hash, perfil) VALUES (?, ?, ?, ?)",
                       ("Administrador Conslin", "admin", gerar_hash_senha("conslin123"), "Admin"))

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
# AUTENTICAÇÃO
# ==========================================
def autenticar_usuario(usuario_input, senha_input):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, usuario, senha_hash, perfil FROM usuarios WHERE usuario = ?", (usuario_input.strip().lower(),))
    res = cursor.fetchone()
    conn.close()
    if res and verificar_senha_hash(senha_input, res[3]):
        return {"id": res[0], "nome": res[1], "usuario": res[2], "perfil": res[4]}
    return None

def tela_login():
    if "usuario_logado" not in st.session_state:
        st.session_state["usuario_logado"] = None

    if st.session_state["usuario_logado"] is None:
        st.title("🔒 Acesso Restrito - Conslin")
        with st.form("form_login"):
            usuario = st.text_input("Usuário").strip().lower()
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                dados_user = autenticar_usuario(usuario, senha)
                if dados_user:
                    st.session_state["usuario_logado"] = dados_user
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
        "Atendente": ["Dashboard & Metas", "Cadastro de Clientes", "Novo Atendimento / Orçamento", "Gestão de Atendimentos", "Contas e Parcelas a Receber"],
        "Admin": ["Dashboard & Metas", "Cadastro de Clientes", "Novo Atendimento / Orçamento", "Gestão de Atendimentos", "Contas e Parcelas a Receber", "Prestadores & Fornecedores", "Contas a Pagar, Dívidas & Acordos", "Registrar Pagamentos", "Fluxo de Caixa & DRE", "⚙️ Gerenciar Usuários"]
    }
    menu = st.sidebar.radio("Navegação", menus_por_perfil.get(perfil_usuario, menus_por_perfil["Atendente"]))

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
            status_validos = ["Aprovado / Execução", "Concluído", "Em Orçamento"]
            df_aprovados = df_atendimentos[df_atendimentos['status'].isin(status_validos)].copy()
        else:
            df_aprovados = pd.DataFrame(columns=['categoria', 'valor_fechado', 'valor_orcamento', 'data_dt'])

        hoje = date.today()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        inicio_mes = hoje.replace(day=1)
        inicio_ano = hoje.replace(month=1, day=1)

        if perfil_usuario == "Admin":
            with st.expander("⚙️ Configurar Metas por Categoria"):
                with st.form("form_metas_completas"):
                    novas_m, novas_s, novas_d = {}, {}, {}
                    for cat in CATEGORIAS:
                        st.markdown(f"**📍 {cat}**")
                        row_cat = df_metas[df_metas['categoria'] == cat] if not df_metas.empty and cat in df_metas['categoria'].values else pd.DataFrame()
                        c1, c2, c3 = st.columns(3)
                        novas_m[cat] = c1.number_input(f"Meta Mensal ({cat})", value=float(row_cat['meta_valor'].values[0]) if not row_cat.empty else 0.0, step=500.0)
                        novas_s[cat] = c2.number_input(f"Meta Semanal ({cat})", value=float(row_cat['meta_semanal'].values[0]) if not row_cat.empty else 0.0, step=100.0)
                        novas_d[cat] = c3.number_input(f"Meta Diária ({cat})", value=float(row_cat['meta_diaria'].values[0]) if not row_cat.empty else 0.0, step=50.0)
                    if st.form_submit_button("💾 Salvar Metas"):
                        conn = conectar()
                        cursor = conn.cursor()
                        for cat in CATEGORIAS:
                            cursor.execute("UPDATE metas SET meta_diaria = ?, meta_semanal = ?, meta_valor = ? WHERE categoria = ?", (novas_d[cat], novas_s[cat], novas_m[cat], cat))
                        conn.commit()
                        conn.close()
                        st.success("Metas atualizadas!")
                        st.rerun()

        st.subheader("📊 Resumo Geral")
        if not df_aprovados.empty:
            df_aprovados['valor_real'] = df_aprovados.apply(lambda r: r['valor_fechado'] if r['valor_fechado'] > 0 else r['valor_orcamento'], axis=1)
            
            val_hoje = df_aprovados[df_aprovados['data_dt'] == hoje]['valor_real'].sum()
            val_semana = df_aprovados[df_aprovados['data_dt'] >= inicio_semana]['valor_real'].sum()
            val_mes = df_aprovados[df_aprovados['data_dt'] >= inicio_mes]['valor_real'].sum()
            val_ano = df_aprovados[df_aprovados['data_dt'] >= inicio_ano]['valor_real'].sum()
        else:
            val_hoje = val_semana = val_mes = val_ano = 0.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Vendas Hoje", f"R$ {val_hoje:,.2f}")
        c2.metric("Vendas Semana", f"R$ {val_semana:,.2f}")
        c3.metric("Vendas Mês", f"R$ {val_mes:,.2f}")
        c4.metric("Acumulado Ano", f"R$ {val_ano:,.2f}")

    # ----------------------------------------------------
    # CADASTRO DE CLIENTES (COM EDITAR E EXCLUIR)
    # ----------------------------------------------------
    elif menu == "Cadastro de Clientes":
        st.header("👤 Cadastro e Seleção de Clientes")
        with st.expander("➕ Novo Cliente", expanded=True):
            with st.form("form_cliente"):
                nome = st.text_input("Nome / Razão Social *")
                telefone = st.text_input("Telefone")
                email = st.text_input("E-mail")
                cpf_cnpj = st.text_input("CPF / CNPJ")
                endereco = st.text_area("Endereço")
                if st.form_submit_button("Cadastrar Cliente"):
                    if nome:
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO clientes (nome, telefone, email, cpf_cnpj, endereco) VALUES (?,?,?,?,?)", (nome, telefone, email, cpf_cnpj, endereco))
                        conn.commit()
                        conn.close()
                        st.success("Cliente cadastrado com sucesso!")
                        st.rerun()

        st.subheader("📋 Lista de Clientes")
        conn = conectar()
        df_cli = pd.read_sql_query("SELECT * FROM clientes ORDER BY id DESC", conn)
        conn.close()

        if not df_cli.empty:
            c_id, c_nome, c_tel, c_email, c_cpf, c_edt, c_del = st.columns([0.6, 2, 1.5, 2, 1.5, 0.8, 0.8])
            c_id.markdown("**ID**"); c_nome.markdown("**Nome**"); c_tel.markdown("**Telefone**"); c_email.markdown("**E-mail**"); c_cpf.markdown("**CPF/CNPJ**"); c_edt.markdown("**Editar**"); c_del.markdown("**Excluir**")
            st.divider()

            for _, row in df_cli.iterrows():
                col_id, col_nome, col_tel, col_email, col_cpf, col_edt, col_del = st.columns([0.6, 2, 1.5, 2, 1.5, 0.8, 0.8])
                col_id.write(row['id'])
                col_nome.write(row['nome'])
                col_tel.write(row['telefone'] or "-")
                col_email.write(row['email'] or "-")
                col_cpf.write(row['cpf_cnpj'] or "-")

                if col_edt.button("✏️", key=f"edit_cli_{row['id']}"):
                    st.session_state["edit_cli_id"] = row['id']
                    st.rerun()

                if col_del.button("🗑️", key=f"del_cli_{row['id']}"):
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM clientes WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.success("Cliente removido!")
                    st.rerun()

            if "edit_cli_id" in st.session_state and st.session_state["edit_cli_id"] is not None:
                id_e = st.session_state["edit_cli_id"]
                reg_e = df_cli[df_cli['id'] == id_e].iloc[0]
                st.divider()
                st.subheader(f"✏️ Editando Cliente #{id_e}")
                with st.form("form_edit_cli"):
                    enome = st.text_input("Nome", value=reg_e['nome'])
                    etelef = st.text_input("Telefone", value=reg_e['telefone'] or "")
                    eemail = st.text_input("E-mail", value=reg_e['email'] or "")
                    ecpf = st.text_input("CPF/CNPJ", value=reg_e['cpf_cnpj'] or "")
                    eend = st.text_area("Endereço", value=reg_e['endereco'] or "")
                    
                    s1, s2 = st.columns(2)
                    if s1.form_submit_button("💾 Salvar"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE clientes SET nome=?, telefone=?, email=?, cpf_cnpj=?, endereco=? WHERE id=?", (enome, etelef, eemail, ecpf, eend, id_e))
                        conn.commit(); conn.close()
                        st.session_state["edit_cli_id"] = None
                        st.success("Cliente atualizado!")
                        st.rerun()
                    if s2.form_submit_button("❌ Cancelar"):
                        st.session_state["edit_cli_id"] = None
                        st.rerun()

    # ----------------------------------------------------
    # NOVO ATENDIMENTO / ORÇAMENTO
    # ----------------------------------------------------
    elif menu == "Novo Atendimento / Orçamento":
        st.header("📝 Registrar Novo Atendimento")
        conn = conectar()
        df_clientes = pd.read_sql_query("SELECT id, nome FROM clientes", conn)
        conn.close()

        if df_clientes.empty:
            st.warning("Cadastre um cliente primeiro.")
        else:
            opcoes_clientes = {f"{row['nome']} (ID: {row['id']})": row['id'] for _, row in df_clientes.iterrows()}
            with st.form("form_atendimento"):
                cliente_sel = st.selectbox("Selecione o Cliente", list(opcoes_clientes.keys()))
                categoria = st.selectbox("Categoria", CATEGORIAS)
                status = st.selectbox("Status", STATUS_OPCOES, index=0)
                descricao = st.text_area("Descrição")
                valor_orcamento = st.number_input("Valor Orçamento (R$)", value=0.0)
                valor_fechado = st.number_input("Valor Fechado (R$)", value=0.0)
                despesas = st.number_input("Despesas (R$)", value=0.0)
                data_contato = st.date_input("Data", value=date.today())
                gerar_rec = st.checkbox("Gerar Conta a Receber automaticamente", value=True)

                if st.form_submit_button("Salvar Atendimento"):
                    c_id = opcoes_clientes[cliente_sel]
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, data_contato)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (c_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, str(data_contato)))
                    
                    at_id = cursor.lastrowid
                    val_para_receber = valor_fechado if valor_fechado > 0 else valor_orcamento
                    if gerar_rec and status in ["Aprovado / Execução", "Concluído", "Em Orçamento"] and val_para_receber > 0:
                        cursor.execute("INSERT INTO contas_receber (cliente_id, atendimento_id, descricao, valor, data_vencimento, status) VALUES (?, ?, ?, ?, ?, 'Pendente')",
                                       (c_id, at_id, f"Fechamento - {categoria}", val_para_receber, str(data_contato)))

                    conn.commit(); conn.close()
                    st.success("Atendimento gravado!")
                    st.rerun()

    # ----------------------------------------------------
    # GESTÃO DE ATENDIMENTOS (COM EDITAR E EXCLUIR)
    # ----------------------------------------------------
    elif menu == "Gestão de Atendimentos":
        st.header("📋 Gestão e Funil de Atendimentos")
        conn = conectar()
        query = """
        SELECT a.id, c.nome as Cliente, a.cliente_id, a.categoria as Categoria, a.status as Status, 
               a.valor_orcamento as [Orçado (R$)], a.valor_fechado as [Fechado (R$)], 
               a.despesas as [Despesas (R$)], a.descricao as Descrição, a.data_contato as Data
        FROM atendimentos a
        LEFT JOIN clientes c ON a.cliente_id = c.id
        ORDER BY a.id DESC
        """
        df_at = pd.read_sql_query(query, conn)
        conn.close()

        if not df_at.empty:
            c_id, c_cli, c_cat, c_stat, c_orc, c_fec, c_edt, c_del = st.columns([0.6, 2, 1.5, 1.5, 1.2, 1.2, 0.8, 0.8])
            c_id.markdown("**ID**"); c_cli.markdown("**Cliente**"); c_cat.markdown("**Categoria**"); c_stat.markdown("**Status**"); c_orc.markdown("**Orçado**"); c_fec.markdown("**Fechado**"); c_edt.markdown("**Editar**"); c_del.markdown("**Excluir**")
            st.divider()

            for _, row in df_at.iterrows():
                col_id, col_cli, col_cat, col_stat, col_orc, col_fec, col_edt, col_del = st.columns([0.6, 2, 1.5, 1.5, 1.2, 1.2, 0.8, 0.8])
                col_id.write(row['id'])
                col_cli.write(row['Cliente'])
                col_cat.write(row['Categoria'])
                col_stat.write(row['Status'])
                col_orc.write(f"R$ {row['Orçado (R$)']:,.2f}")
                col_fec.write(f"R$ {row['Fechado (R$)']:,.2f}")

                if col_edt.button("✏️", key=f"edit_at_{row['id']}"):
                    st.session_state["edit_at_id"] = row['id']
                    st.rerun()

                if col_del.button("🗑️", key=f"del_at_{row['id']}"):
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM atendimentos WHERE id = ?", (row['id'],))
                    conn.commit(); conn.close()
                    st.success("Atendimento excluído!")
                    st.rerun()

            if "edit_at_id" in st.session_state and st.session_state["edit_at_id"] is not None:
                id_at_e = st.session_state["edit_at_id"]
                reg_e = df_at[df_at['id'] == id_at_e].iloc[0]
                st.divider()
                st.subheader(f"✏️ Editando Atendimento #{id_at_e}")
                
                with st.form("form_edit_at"):
                    e_stat = st.selectbox("Status", STATUS_OPCOES, index=STATUS_OPCOES.index(reg_e['Status']))
                    e_orc = st.number_input("Orçado (R$)", value=float(reg_e['Orçado (R$)']))
                    e_fec = st.number_input("Fechado (R$)", value=float(reg_e['Fechado (R$)']))
                    e_desp = st.number_input("Despesas (R$)", value=float(reg_e['Despesas (R$)']))
                    e_desc = st.text_area("Descrição", value=reg_e['Descrição'] or "")

                    b1, b2 = st.columns(2)
                    if b1.form_submit_button("💾 Salvar Alterações"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE atendimentos SET status=?, valor_orcamento=?, valor_fechado=?, despesas=?, descricao=? WHERE id=?",
                                       (e_stat, e_orc, e_fec, e_desp, e_desc, id_at_e))
                        conn.commit(); conn.close()
                        st.session_state["edit_at_id"] = None
                        st.success("Atendimento atualizado!")
                        st.rerun()

                    if b2.form_submit_button("❌ Cancelar"):
                        st.session_state["edit_at_id"] = None
                        st.rerun()

    # ----------------------------------------------------
    # CONTAS E PARCELAS A RECEBER (COM EDITAR E EXCLUIR)
    # ----------------------------------------------------
    elif menu == "Contas e Parcelas a Receber":
        st.header("💵 Lançamento e Controle de Contas a Receber")
        conn = conectar()
        df_clientes = pd.read_sql_query("SELECT id, nome FROM clientes", conn)
        conn.close()

        if df_clientes.empty:
            st.warning("Cadastre um cliente primeiro.")
        else:
            opcoes_clientes = {f"{row['nome']} (ID: {row['id']})": row['id'] for _, row in df_clientes.iterrows()}

            with st.expander("➕ Lançar Nova Conta a Receber"):
                with st.form("form_contas_receber"):
                    cliente_sel = st.selectbox("Cliente", list(opcoes_clientes.keys()))
                    descricao = st.text_input("Descrição")
                    valor = st.number_input("Valor (R$)", min_value=0.01, step=100.0)
                    data_vencimiento = st.date_input("Vencimento", value=date.today())
                    status_rec = st.selectbox("Status", ["Pendente", "Recebido"])

                    if st.form_submit_button("Lançar Valor"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO contas_receber (cliente_id, descricao, valor, data_vencimento, status) VALUES (?, ?, ?, ?, ?)",
                                       (opcoes_clientes[cliente_sel], descricao, valor, str(data_vencimiento), status_rec))
                        conn.commit(); conn.close()
                        st.success("Previsão salva!")
                        st.rerun()

            st.subheader("📋 Lista de Recebimentos")
            conn = conectar()
            df_rec = pd.read_sql_query("""
            SELECT cr.id, cr.cliente_id, c.nome as Cliente, cr.descricao as Descrição, cr.valor as [Valor (R$)], 
                   cr.data_vencimento as Vencimento, cr.status as Status
            FROM contas_receber cr LEFT JOIN clientes c ON cr.cliente_id = c.id ORDER BY cr.data_vencimento ASC
            """, conn)
            conn.close()

            if not df_rec.empty:
                c_id, c_cli, c_desc, c_val, c_venc, c_stat, c_edt, c_del = st.columns([0.6, 2, 2, 1.2, 1.2, 1, 0.8, 0.8])
                c_id.markdown("**ID**"); c_cli.markdown("**Cliente**"); c_desc.markdown("**Descrição**"); c_val.markdown("**Valor**"); c_venc.markdown("**Vencimento**"); c_stat.markdown("**Status**"); c_edt.markdown("**Editar**"); c_del.markdown("**Excluir**")
                st.divider()

                for _, row in df_rec.iterrows():
                    col_id, col_cli, col_desc, col_val, col_venc, col_stat, col_edt, col_del = st.columns([0.6, 2, 2, 1.2, 1.2, 1, 0.8, 0.8])
                    col_id.write(row['id'])
                    col_cli.write(row['Cliente'])
                    col_desc.write(row['Descrição'] or "-")
                    col_val.write(f"R$ {row['Valor (R$)']:,.2f}")
                    col_venc.write(row['Vencimento'])
                    col_stat.write(row['Status'])

                    if col_edt.button("✏️", key=f"edit_rec_{row['id']}"):
                        st.session_state["edit_rec_id"] = row['id']
                        st.rerun()

                    if col_del.button("🗑️", key=f"del_rec_{row['id']}"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM contas_receber WHERE id = ?", (row['id'],))
                        conn.commit(); conn.close()
                        st.success("Lançamento excluído!")
                        st.rerun()

                if "edit_rec_id" in st.session_state and st.session_state["edit_rec_id"] is not None:
                    rec_id_e = st.session_state["edit_rec_id"]
                    reg_e = df_rec[df_rec['id'] == rec_id_e].iloc[0]
                    st.divider()
                    st.subheader(f"✏️ Editando Lançamento #{rec_id_e}")
                    with st.form("form_edit_rec"):
                        e_desc = st.text_input("Descrição", value=reg_e['Descrição'] or "")
                        e_val = st.number_input("Valor (R$)", value=float(reg_e['Valor (R$)']))
                        e_venc = st.date_input("Vencimento", value=datetime.strptime(reg_e['Vencimento'], "%Y-%m-%d").date() if reg_e['Vencimento'] else date.today())
                        e_stat = st.selectbox("Status", ["Pendente", "Recebido"], index=0 if reg_e['Status'] == 'Pendente' else 1)

                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("💾 Salvar"):
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE contas_receber SET descricao=?, valor=?, data_vencimento=?, status=? WHERE id=?", (e_desc, e_val, str(e_venc), e_stat, rec_id_e))
                            conn.commit(); conn.close()
                            st.session_state["edit_rec_id"] = None
                            st.success("Lançamento atualizado!")
                            st.rerun()
                        if b2.form_submit_button("❌ Cancelar"):
                            st.session_state["edit_rec_id"] = None
                            st.rerun()

    # ----------------------------------------------------
    # PRESTADORES & FORNECEDORES (COM EDITAR E EXCLUIR)
    # ----------------------------------------------------
    elif menu == "Prestadores & Fornecedores":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso restrito ao Administrador.")
        else:
            st.header("👷 Cadastrar Prestadores e Fornecedores")
            with st.expander("➕ Novo Cadastramento"):
                with st.form("form_parceiro"):
                    nome = st.text_input("Nome / Razão Social *")
                    tipo = st.selectbox("Tipo", TIPOS_PARCEIROS)
                    telefone = st.text_input("Telefone")
                    cpf_cnpj = st.text_input("CPF / CNPJ")
                    chave_pix = st.text_input("Chave PIX")
                    observacao = st.text_area("Observações")
                    if st.form_submit_button("Cadastrar"):
                        if nome:
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO parceiros (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao) VALUES (?,?,?,?,?,?)",
                                           (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao))
                            conn.commit(); conn.close()
                            st.success("Parceiro cadastrado!")
                            st.rerun()

            st.subheader("📋 Lista de Parceiros")
            conn = conectar()
            df_parc = pd.read_sql_query("SELECT * FROM parceiros ORDER BY id DESC", conn)
            conn.close()

            if not df_parc.empty:
                c_id, c_nome, c_tipo, c_tel, c_pix, c_edt, c_del = st.columns([0.6, 2, 1.5, 1.5, 1.5, 0.8, 0.8])
                c_id.markdown("**ID**"); c_nome.markdown("**Nome**"); c_tipo.markdown("**Tipo**"); c_tel.markdown("**Telefone**"); c_pix.markdown("**PIX**"); c_edt.markdown("**Editar**"); c_del.markdown("**Excluir**")
                st.divider()

                for _, row in df_parc.iterrows():
                    col_id, col_nome, col_tipo, col_tel, col_pix, col_edt, col_del = st.columns([0.6, 2, 1.5, 1.5, 1.5, 0.8, 0.8])
                    col_id.write(row['id'])
                    col_nome.write(row['nome'])
                    col_tipo.write(row['tipo'])
                    col_tel.write(row['telefone'] or "-")
                    col_pix.write(row['chave_pix'] or "-")

                    if col_edt.button("✏️", key=f"edit_parc_{row['id']}"):
                        st.session_state["edit_parc_id"] = row['id']
                        st.rerun()

                    if col_del.button("🗑️", key=f"del_parc_{row['id']}"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM parceiros WHERE id = ?", (row['id'],))
                        conn.commit(); conn.close()
                        st.success("Registro removido!")
                        st.rerun()

                if "edit_parc_id" in st.session_state and st.session_state["edit_parc_id"] is not None:
                    p_id_e = st.session_state["edit_parc_id"]
                    reg_e = df_parc[df_parc['id'] == p_id_e].iloc[0]
                    st.divider()
                    st.subheader(f"✏️ Editando Parceiro #{p_id_e}")
                    with st.form("form_edit_parc"):
                        enome = st.text_input("Nome", value=reg_e['nome'])
                        etipo = st.selectbox("Tipo", TIPOS_PARCEIROS, index=TIPOS_PARCEIROS.index(reg_e['tipo']))
                        etelef = st.text_input("Telefone", value=reg_e['telefone'] or "")
                        ecpf = st.text_input("CPF/CNPJ", value=reg_e['cpf_cnpj'] or "")
                        epix = st.text_input("Chave PIX", value=reg_e['chave_pix'] or "")
                        eobs = st.text_area("Observações", value=reg_e['observacao'] or "")

                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("💾 Salvar"):
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE parceiros SET nome=?, tipo=?, telefone=?, cpf_cnpj=?, chave_pix=?, observacao=? WHERE id=?",
                                           (enome, etipo, etelef, ecpf, epix, eobs, p_id_e))
                            conn.commit(); conn.close()
                            st.session_state["edit_parc_id"] = None
                            st.success("Cadastro atualizado!")
                            st.rerun()
                        if b2.form_submit_button("❌ Cancelar"):
                            st.session_state["edit_parc_id"] = None
                            st.rerun()

    # ----------------------------------------------------
    # CONTAS A PAGAR, DÍVIDAS & ACORDOS (COM EDITAR E EXCLUIR)
    # ----------------------------------------------------
    elif menu == "Contas a Pagar, Dívidas & Acordos":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso restrito ao Administrador.")
        else:
            st.header("💸 Contas a Pagar e Dívidas")
            conn = conectar()
            df_parceiros = pd.read_sql_query("SELECT id, nome, tipo FROM parceiros", conn)
            conn.close()

            if df_parceiros.empty:
                st.warning("Cadastre um fornecedor ou prestador primeiro.")
            else:
                opcoes_parceiros = {f"{row['nome']} ({row['tipo']} - ID: {row['id']})": row['id'] for _, row in df_parceiros.iterrows()}
                with st.expander("➕ Lançar Conta a Pagar"):
                    with st.form("form_contas"):
                        parceiro_sel = st.selectbox("Credor", list(opcoes_parceiros.keys()))
                        tipo_conta = st.selectbox("Tipo", TIPOS_CONTAS)
                        descricao = st.text_input("Descrição")
                        valor = st.number_input("Valor (R$)", min_value=0.01, step=50.0)
                        data_vencimento = st.date_input("Vencimento")
                        status = st.selectbox("Status", ["Pendente", "Acordado / Parcelado", "Pago"])
                        
                        if st.form_submit_button("Salvar Conta"):
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO contas_pagar (parceiro_id, descricao, tipo_conta, valor, data_vencimento, status) VALUES (?, ?, ?, ?, ?, ?)",
                                           (opcoes_parceiros[parceiro_sel], descricao, tipo_conta, valor, str(data_vencimento), status))
                            conn.commit(); conn.close()
                            st.success("Conta cadastrada!")
                            st.rerun()

            st.subheader("📋 Relação de Contas a Pagar")
            conn = conectar()
            df_pag = pd.read_sql_query("""
            SELECT cp.id, p.nome as Credor, cp.tipo_conta as Tipo, cp.descricao as Descrição, 
                   cp.valor as [Valor (R$)], cp.data_vencimento as Vencimento, cp.status as Status
            FROM contas_pagar cp LEFT JOIN parceiros p ON cp.parceiro_id = p.id ORDER BY cp.data_vencimento ASC
            """, conn)
            conn.close()

            if not df_pag.empty:
                c_id, c_cred, c_tipo, c_desc, c_val, c_venc, c_stat, c_edt, c_del = st.columns([0.6, 1.5, 1.2, 1.5, 1.2, 1.2, 1, 0.8, 0.8])
                c_id.markdown("**ID**"); c_cred.markdown("**Credor**"); c_tipo.markdown("**Tipo**"); c_desc.markdown("**Descrição**"); c_val.markdown("**Valor**"); c_venc.markdown("**Vencimento**"); c_stat.markdown("**Status**"); c_edt.markdown("**Editar**"); c_del.markdown("**Excluir**")
                st.divider()

                for _, row in df_pag.iterrows():
                    col_id, col_cred, col_tipo, col_desc, col_val, col_venc, col_stat, col_edt, col_del = st.columns([0.6, 1.5, 1.2, 1.5, 1.2, 1.2, 1, 0.8, 0.8])
                    col_id.write(row['id'])
                    col_cred.write(row['Credor'])
                    col_tipo.write(row['Tipo'])
                    col_desc.write(row['Descrição'])
                    col_val.write(f"R$ {row['Valor (R$)']:,.2f}")
                    col_venc.write(row['Vencimento'])
                    col_stat.write(row['Status'])

                    if col_edt.button("✏️", key=f"edit_pag_{row['id']}"):
                        st.session_state["edit_pag_id"] = row['id']
                        st.rerun()

                    if col_del.button("🗑️", key=f"del_pag_{row['id']}"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM contas_pagar WHERE id = ?", (row['id'],))
                        conn.commit(); conn.close()
                        st.success("Conta deletada!")
                        st.rerun()

                if "edit_pag_id" in st.session_state and st.session_state["edit_pag_id"] is not None:
                    pag_id_e = st.session_state["edit_pag_id"]
                    reg_e = df_pag[df_pag['id'] == pag_id_e].iloc[0]
                    st.divider()
                    st.subheader(f"✏️ Editando Conta #{pag_id_e}")
                    with st.form("form_edit_pag"):
                        e_desc = st.text_input("Descrição", value=reg_e['Descrição'])
                        e_tipo = st.selectbox("Tipo", TIPOS_CONTAS, index=TIPOS_CONTAS.index(reg_e['Tipo']) if reg_e['Tipo'] in TIPOS_CONTAS else 0)
                        e_val = st.number_input("Valor (R$)", value=float(reg_e['Valor (R$)']))
                        e_venc = st.date_input("Vencimento", value=datetime.strptime(reg_e['Vencimento'], "%Y-%m-%d").date() if reg_e['Vencimento'] else date.today())
                        e_stat = st.selectbox("Status", ["Pendente", "Acordado / Parcelado", "Pago"], index=["Pendente", "Acordado / Parcelado", "Pago"].index(reg_e['Status']))

                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("💾 Salvar"):
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE contas_pagar SET descricao=?, tipo_conta=?, valor=?, data_vencimento=?, status=? WHERE id=?",
                                           (e_desc, e_tipo, e_val, str(e_venc), e_stat, pag_id_e))
                            conn.commit(); conn.close()
                            st.session_state["edit_pag_id"] = None
                            st.success("Conta atualizada!")
                            st.rerun()
                        if b2.form_submit_button("❌ Cancelar"):
                            st.session_state["edit_pag_id"] = None
                            st.rerun()

    # ----------------------------------------------------
    # REGISTRAR PAGAMENTOS
    # ----------------------------------------------------
    elif menu == "Registrar Pagamentos":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso restrito ao Administrador.")
        else:
            st.header("💳 Registrar Pagamento Efetuado")
            conn = conectar()
            df_pendentes = pd.read_sql_query("SELECT cp.id, p.nome as Credor, cp.descricao, cp.valor, cp.data_vencimento, cp.parceiro_id FROM contas_pagar cp LEFT JOIN parceiros p ON cp.parceiro_id = p.id WHERE cp.status != 'Pago'", conn)
            conn.close()

            if df_pendentes.empty:
                st.info("Nenhuma conta pendente para pagamento.")
            else:
                opcoes_contas = {f"ID {row['id']} - {row['Credor']} - {row['descricao']} - R$ {row['valor']:,.2f}": row for _, row in df_pendentes.iterrows()}
                conta_sel = st.selectbox("Selecione a Conta", list(opcoes_contas.keys()))
                dados_conta = opcoes_contas[conta_sel]

                with st.form("form_pagamento"):
                    valor_pago = st.number_input("Valor Pago (R$)", value=float(dados_conta['valor']), step=10.0)
                    forma_pagamento = st.selectbox("Forma de Pagamento", ["PIX", "Transferência Bancária", "Dinheiro", "Boleto", "Cartão"])
                    comprovante = st.text_input("Comprovante / Obs")
                    data_pagamento = st.date_input("Data do Pagamento")

                    if st.form_submit_button("Confirmar Pagamento"):
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO pagamentos (conta_id, parceiro_id, valor_pago, data_pagamento, forma_pagamento, comprovante_ref) VALUES (?, ?, ?, ?, ?, ?)",
                                       (dados_conta['id'], dados_conta['parceiro_id'], valor_pago, str(data_pagamento), forma_pagamento, comprovante))
                        
                        if valor_pago >= dados_conta['valor']:
                            cursor.execute("UPDATE contas_pagar SET status = 'Pago' WHERE id = ?", (dados_conta['id'],))
                        else:
                            cursor.execute("UPDATE contas_pagar SET valor = ? WHERE id = ?", (dados_conta['valor'] - valor_pago, dados_conta['id']))

                        conn.commit(); conn.close()
                        st.success("Pagamento efetuado!")
                        st.rerun()

            st.subheader("📜 Histórico de Pagamentos")
            conn = conectar()
            df_hist = pd.read_sql_query("SELECT pg.id, p.nome as Beneficiário, pg.valor_pago as [Valor Pago (R$)], pg.data_pagamento as Data, pg.forma_pagamento as Forma FROM pagamentos pg LEFT JOIN parceiros p ON pg.parceiro_id = p.id", conn)
            conn.close()
            st.dataframe(df_hist, use_container_width=True)

    # ----------------------------------------------------
    # FLUXO DE CAIXA & DRE
    # ----------------------------------------------------
    elif menu == "Fluxo de Caixa & DRE":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso restrito ao Administrador.")
        else:
            st.header("💰 Fluxo de Caixa e Projeção Financeira")
            conn = conectar()
            df_rec = pd.read_sql_query("SELECT * FROM contas_receber WHERE status = 'Pendente'", conn)
            df_pag = pd.read_sql_query("SELECT * FROM contas_pagar WHERE status != 'Pago'", conn)
            conn.close()

            rec_tot = df_rec['valor'].sum() if not df_rec.empty else 0.0
            pag_tot = df_pag['valor'].sum() if not df_pag.empty else 0.0

            c1, c2, c3 = st.columns(3)
            c1.metric("Total a Receber (Pendente)", f"R$ {rec_tot:,.2f}")
            c2.metric("Total a Pagar (Aberto)", f"R$ {pag_tot:,.2f}")
            c3.metric("Saldo Projetado", f"R$ {(rec_tot - pag_tot):,.2f}")

    # ----------------------------------------------------
    # GERENCIAR USUÁRIOS (COM EDITAR E EXCLUIR)
    # ----------------------------------------------------
    elif menu == "⚙️ Gerenciar Usuários":
        if perfil_usuario != "Admin":
            st.error("🚫 Acesso restrito ao Administrador.")
        else:
            st.header("⚙️ Gestão de Usuários")
            with st.expander("➕ Novo Usuário"):
                with st.form("form_novo_usuario"):
                    nome_novo = st.text_input("Nome Completo")
                    login_novo = st.text_input("Login").strip().lower()
                    senha_nova = st.text_input("Senha", type="password")
                    perfil_novo = st.selectbox("Perfil", ["Atendente", "Admin"])
                    
                    if st.form_submit_button("Cadastrar Usuário"):
                        if nome_novo and login_novo and senha_nova:
                            conn = conectar()
                            cursor = conn.cursor()
                            try:
                                cursor.execute("INSERT INTO usuarios (nome, usuario, senha_hash, perfil) VALUES (?, ?, ?, ?)",
                                               (nome_novo, login_novo, gerar_hash_senha(senha_nova), perfil_novo))
                                conn.commit()
                                st.success(f"Usuário {login_novo} cadastrado!")
                            except sqlite3.IntegrityError:
                                st.error("Login já existente.")
                            finally:
                                conn.close()

            st.subheader("👥 Usuários Cadastrados")
            conn = conectar()
            df_usr = pd.read_sql_query("SELECT id, nome, usuario, perfil FROM usuarios ORDER BY id ASC", conn)
            conn.close()

            if not df_usr.empty:
                c_id, c_nome, c_login, c_perf, c_edt, c_del = st.columns([0.6, 2, 2, 1.5, 0.8, 0.8])
                c_id.markdown("**ID**"); c_nome.markdown("**Nome**"); c_login.markdown("**Login**"); c_perf.markdown("**Perfil**"); c_edt.markdown("**Editar**"); c_del.markdown("**Excluir**")
                st.divider()

                for _, row in df_usr.iterrows():
                    col_id, col_nome, col_login, col_perf, col_edt, col_del = st.columns([0.6, 2, 2, 1.5, 0.8, 0.8])
                    col_id.write(row['id'])
                    col_nome.write(row['nome'])
                    col_login.write(row['usuario'])
                    col_perf.write(row['perfil'])

                    if col_edt.button("✏️", key=f"edit_usr_{row['id']}"):
                        st.session_state["edit_usr_id"] = row['id']
                        st.rerun()

                    if col_del.button("🗑️", key=f"del_usr_{row['id']}"):
                        if row['usuario'] == "admin":
                            st.error("Não é possível excluir o administrador padrão!")
                        else:
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM usuarios WHERE id = ?", (row['id'],))
                            conn.commit(); conn.close()
                            st.success("Usuário removido!")
                            st.rerun()

                if "edit_usr_id" in st.session_state and st.session_state["edit_usr_id"] is not None:
                    u_id_e = st.session_state["edit_usr_id"]
                    reg_e = df_usr[df_usr['id'] == u_id_e].iloc[0]
                    st.divider()
                    st.subheader(f"✏️ Editando Usuário #{u_id_e}")
                    with st.form("form_edit_usr"):
                        enome = st.text_input("Nome", value=reg_e['nome'])
                        elogin = st.text_input("Login", value=reg_e['usuario'])
                        eperfil = st.selectbox("Perfil", ["Atendente", "Admin"], index=0 if reg_e['perfil'] == 'Atendente' else 1)
                        esenha = st.text_input("Nova Senha (deixe em branco para manter)", type="password")

                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("💾 Salvar"):
                            conn = conectar()
                            cursor = conn.cursor()
                            if esenha:
                                cursor.execute("UPDATE usuarios SET nome=?, usuario=?, perfil=?, senha_hash=? WHERE id=?",
                                               (enome, elogin, eperfil, gerar_hash_senha(esenha), u_id_e))
                            else:
                                cursor.execute("UPDATE usuarios SET nome=?, usuario=?, perfil=? WHERE id=?",
                                               (enome, elogin, eperfil, u_id_e))
                            conn.commit(); conn.close()
                            st.session_state["edit_usr_id"] = None
                            st.success("Usuário atualizado!")
                            st.rerun()

                        if b2.form_submit_button("❌ Cancelar"):
                            st.session_state["edit_usr_id"] = None
                            st.rerun()
                           
                              
