import streamlit as st
import pandas as pd
import sqlite3

# ==========================================
# 1. AUTENTICAÇÃO E LOGIN
# ==========================================
USUARIO_CORRETO = "admin"
SENHA_CORRETA = "conslin123"  # Altere para a senha desejada

def verificar_login():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.title("🔒 Acesso Restrito - Conslin")
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar")
            
            if btn_login:
                if usuario == USUARIO_CORRETO and senha == SENHA_CORRETA:
                    st.session_state["autenticado"] = True
                    st.success("Acesso liberado!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        return False
    return True

# ==========================================
# 2. BANCO DE DADOS
# ==========================================
def conectar():
    return sqlite3.connect("gestao_escritorio.db")

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()
    
    # Clientes
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
    
    # Atendimentos / Orçamentos
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
    
    # Metas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS metas (
        categoria TEXT PRIMARY KEY,
        meta_valor REAL DEFAULT 0.0
    )
    """)
    
    # Prestadores e Fornecedores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parceiros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL, -- 'Prestador de Serviço', 'Equipe do Escritório', 'Fornecedor'
        telefone TEXT,
        cpf_cnpj TEXT,
        chave_pix TEXT,
        observacao TEXT
    )
    """)
    
    # Contas a Pagar / Dívidas / Acordos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contas_pagar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parceiro_id INTEGER,
        descricao TEXT NOT NULL,
        tipo_conta TEXT NOT NULL, -- 'Dívida', 'Acordo', 'Prestação de Serviço', 'Fornecedor', 'Equipe'
        valor REAL NOT NULL,
        data_vencimento DATE NOT NULL,
        status TEXT NOT NULL, -- 'Pendente', 'Pago', 'Acordado / Parcelado'
        FOREIGN KEY (parceiro_id) REFERENCES parceiros (id)
    )
    """)
    
    # Histórico de Pagamentos Efetuados
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
# 3. INTERFACE PRINCIPAL
# ==========================================
criar_tabelas()

st.set_page_config(page_title="Sistema de Gestão Conslin", layout="wide")

if verificar_login():
    # Botão de Logout na barra lateral
    st.sidebar.write(f"👤 Usuário: **{USUARIO_CORRETO}**")
    if st.sidebar.button("Sair / Logout"):
        st.session_state["autenticado"] = False
        st.rerun()

    CATEGORIAS = ["Documentação", "Pequenos Serviços", "Reforma", "Manutenção", "Venda de Materiais"]
    STATUS_OPCOES = ["Primeiro Contato", "Em Orçamento", "Aprovado / Execução", "Concluído", "Cancelado"]
    TIPOS_PARCEIROS = ["Prestador de Serviço", "Equipe do Escritório", "Fornecedor"]
    TIPOS_CONTAS = ["Dívida", "Acordo", "Prestação de Serviço", "Fornecedor", "Equipe / Salário"]

    st.title("🏗️ Conslin - Gestão Operacional & Financeira")

    menu = st.sidebar.radio("Navegação", [
        "Dashboard & Metas",
        "Cadastro de Clientes",
        "Novo Atendimento / Orçamento",
        "Gestão de Atendimentos",
        "Prestadores & Fornecedores",
        "Contas a Pagar, Dívidas & Acordos",
        "Registrar Pagamentos",
        "Fluxo de Caixa & DRE"
    ])

    # ----------------------------------------------------
    # DASHBOARD & METAS
    # ----------------------------------------------------
    if menu == "Dashboard & Metas":
        st.header("🎯 Painel de Metas e Desempenho por Categoria")
        conn = conectar()
        df_atendimentos = pd.read_sql_query("SELECT * FROM atendimentos", conn)
        df_metas = pd.read_sql_query("SELECT * FROM metas", conn)
        conn.close()

        with st.expander("⚙️ Ajustar Metas de Venda por Categoria"):
            with st.form("form_metas"):
                novas_metas = {}
                for cat in CATEGORIAS:
                    meta_atual = float(df_metas[df_metas['categoria'] == cat]['meta_valor'].values[0]) if not df_metas.empty and cat in df_metas['categoria'].values else 0.0
                    novas_metas[cat] = st.number_input(f"Meta para {cat} (R$)", value=meta_atual, step=500.0)
                if st.form_submit_button("Salvar Metas"):
                    conn = conectar()
                    cursor = conn.cursor()
                    for cat, valor in novas_metas.items():
                        cursor.execute("UPDATE metas SET meta_valor = ? WHERE categoria = ?", (valor, cat))
                    conn.commit()
                    conn.close()
                    st.success("Metas atualizadas com sucesso!")
                    st.rerun()

        st.subheader("Atingimento de Metas (Serviços Aprovados / Concluídos)")
        cols = st.columns(len(CATEGORIAS))
        for i, cat in enumerate(CATEGORIAS):
            meta_val = float(df_metas[df_metas['categoria'] == cat]['meta_valor'].values[0]) if not df_metas.empty and cat in df_metas['categoria'].values else 0.0
            if not df_atendimentos.empty:
                realizado = df_atendimentos[
                    (df_atendimentos['categoria'] == cat) & 
                    (df_atendimentos['status'].isin(["Aprovado / Execução", "Concluído"]))
                ]['valor_fechado'].sum()
            else:
                realizado = 0.0

            percentual = (realizado / meta_val * 100) if meta_val > 0 else 0.0
            with cols[i]:
                st.metric(label=cat, value=f"R$ {realizado:,.2f}", delta=f"{percentual:.1f}% da meta")
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
                if st.form_submit_button("Salvar Atendimento"):
                    cliente_id = opcoes_clientes[cliente_sel]
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas))
                    conn.commit()
                    conn.close()
                    st.success("Atendimento registrado no banco de dados!")

    # ----------------------------------------------------
    # GESTÃO DE ATENDIMENTOS
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
            st.subheader("✏️ Atualizar Status ou Valores")
            atendimento_id = st.number_input("Informe o ID do Atendimento", min_value=1, step=1)
            registro = df_atendimentos[df_atendimentos['id'] == atendimento_id]
            if not registro.empty:
                st.write(f"Editando atendimento do cliente: **{registro.iloc[0]['Cliente']}**")
                with st.form("form_edicao"):
                    novo_status = st.selectbox("Novo Status", STATUS_OPCOES, index=STATUS_OPCOES.index(registro.iloc[0]['Status']))
                    novo_orcamento = st.number_input("Novo Valor Orçado (R$)", value=float(registro.iloc[0]['Orçado (R$)']))
                    novo_fechado = st.number_input("Novo Valor Fechado (R$)", value=float(registro.iloc[0]['Fechado (R$)']))
                    novas_despesas = st.number_input("Novas Despesas (R$)", value=float(registro.iloc[0]['Despesas (R$)']))
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
    # PRESTADORES, EQUIPE E FORNECEDORES
    # ----------------------------------------------------
    elif menu == "Prestadores & Fornecedores":
        st.header("👷 Cadastrar Prestadores, Equipe e Fornecedores")
        with st.form("form_parceiro"):
            nome = st.text_input("Nome / Razão Social *")
            tipo = st.selectbox("Tipo de Cadastro", TIPOS_PARCEIROS)
            telefone = st.text_input("Telefone / WhatsApp")
            cpf_cnpj = st.text_input("CPF ou CNPJ")
            chave_pix = st.text_input("Chave PIX / Dados Bancários")
            observacao = st.text_area("Observações (Especialidade, Condições, etc.)")
            if st.form_submit_button("Cadastrar Cadastrado"):
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
    # CONTAS A PAGAR, DÍVIDAS & ACORDOS
    # ----------------------------------------------------
    elif menu == "Contas a Pagar, Dívidas & Acordos":
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
            st.warning(f" Total Pendente / Em Aberto em Dívidas e Contas: **R$ {pendentes:,.2f}**")

    # ----------------------------------------------------
    # REGISTRAR PAGAMENTOS
    # ----------------------------------------------------
    elif menu == "Registrar Pagamentos":
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
                    # Registrar histórico
                    cursor.execute("""
                    INSERT INTO pagamentos (conta_id, parceiro_id, valor_pago, data_pagamento, forma_pagamento, comprovante_ref)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (dados_conta['id'], dados_conta['parceiro_id'], valor_pago, str(data_pagamento), forma_pagamento, comprovante))
                    
                    # Atualizar conta como Pago se o valor for integral
                    if valor_pago >= dados_conta['valor']:
                        cursor.execute("UPDATE contas_pagar SET status = 'Pago' WHERE id = ?", (dados_conta['id'],))
                    else:
                        # Se pagou parcial, atualiza valor restante
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
    # FLUXO DE CAIXA & DRE
    # ----------------------------------------------------
    elif menu == "Fluxo de Caixa & DRE":
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
       
