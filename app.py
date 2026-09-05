import streamlit as st
import pandas as pd
import sqlite3
import banco

# Garantir que o banco de dados e tabelas existam ao iniciar
banco.criar_tabelas()

st.set_page_config(page_title="Gestão de Atendimentos e Serviços", layout="wide")

CATEGORIAS = ["Documentação", "Pequenos Serviços", "Reforma", "Manutenção", "Venda de Materiais"]
STATUS_OPCOES = ["Primeiro Contato", "Em Orçamento", "Aprovado / Execução", "Concluído", "Cancelado"]

def conectar():
    return sqlite3.connect("gestao_escritorio.db")

st.title("📊 Sistema de Gestão de Atendimentos & Finanças")

menu = st.sidebar.selectbox("Navegação", [
    "Dashboard & Metas",
    "Cadastro de Clientes",
    "Novo Atendimento / Orçamento",
    "Gestão de Atendimentos",
    "Fluxo de Caixa & DRE"
])

# 1. DASHBOARD E METAS
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
                meta_atual = float(df_metas[df_metas['categoria'] == cat]['meta_valor'].values[0]) if not df_metas.empty else 0.0
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
        meta_val = float(df_metas[df_metas['categoria'] == cat]['meta_valor'].values[0]) if not df_metas.empty else 0.0
        if not df_atendimentos.empty:
            realizado = df_atendimentos[
                (df_atendimentos['categoria'] == cat) & 
                (df_atendimentos['status'].isin(["Aprovado / Execução", "Concluído"]))
            ]['valor_fechado'].sum()
        else:
            realizado = 0.0

        percentual = (realizado / meta_val * 100) if meta_val > 0 else 0.0
        
        with cols[i]:
            st.metric(
                label=cat, 
                value=f"R$ {realizado:,.2f}", 
                delta=f"{percentual:.1f}% da meta (R$ {meta_val:,.2f})"
            )
            st.progress(min(percentual / 100, 1.0))

# 2. CADASTRO DE CLIENTES
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

# 3. NOVO ATENDIMENTO / ORÇAMENTO
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
            despesas = st.number_input("Despesas Previstas/Incorridas (R$)", value=0.0, step=50.0)
            
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

# 4. GESTÃO DE ATENDIMENTOS E MUDANÇA DE STATUS
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
        
        st.subheader("✏️ Atualizar Status ou Valores de um Atendimento")
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

# 5. FLUXO DE CAIXA & DRE
elif menu == "Fluxo de Caixa & DRE":
    st.header("💰 Fluxo de Caixa e Lucratividade por Categoria")
    
    conn = conectar()
    df = pd.read_sql_query("""
    SELECT categoria, 
           SUM(valor_orcamento) as total_orcado,
           SUM(valor_fechado) as receita_total,
           SUM(despesas) as despesa_total
    FROM atendimentos
    WHERE status IN ('Aprovado / Execução', 'Concluído')
    GROUP BY categoria
    """, conn)
    conn.close()

    if df.empty:
        st.info("Ainda não existem serviços aprovados ou concluídos para gerar relatórios financeiros.")
    else:
        df['lucro_liquido'] = df['receita_total'] - df['despesa_total']
        df['margem_lucro_%'] = (df['lucro_liquido'] / df['receita_total'] * 100).fillna(0)
        
        st.subheader("Resumo por Categoria (Serviços Aprovados e Concluídos)")
        st.dataframe(
            df.rename(columns={
                'categoria': 'Categoria',
                'total_orcado': 'Total Orçado (R$)',
                'receita_total': 'Receita/Vendas (R$)',
                'despesa_total': 'Despesas Totais (R$)',
                'lucro_liquido': 'Lucro Líquido (R$)',
                'margem_lucro_%': 'Margem (%)'
            }),
            use_container_width=True
        )

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        receita_geral = df['receita_total'].sum()
        despesa_geral = df['despesa_total'].sum()
        lucro_geral = receita_geral - despesa_geral
        
        c1.metric("Receita Total (Fechada)", f"R$ {receita_geral:,.2f}")
        c2.metric("Despesas Totais", f"R$ {despesa_geral:,.2f}")
        c3.metric("Lucro Líquido Geral", f"R$ {lucro_geral:,.2f}")
