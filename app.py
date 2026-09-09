import hashlib
import sqlite3
from datetime import date, datetime, timedelta

from fpdf import FPDF
import pandas as pd
import streamlit as st


# ==========================================
# FUNÇÃO PARA GERAR PDF EM MEMÓRIA (fpdf2)
# ==========================================
class PDFRelatorio(FPDF):

  def header(self):
    self.set_font('Arial', 'B', 14)
    self.cell(
        0,
        10,
        'Conslin - Gestão Operacional & Financeira',
        border=False,
        ln=True,
        align='C',
    )
    self.set_font('Arial', 'I', 9)
    self.cell(
        0,
        5,
        'Relatório Gerencial Emitido via Sistema',
        border=False,
        ln=True,
        align='C',
    )
    self.ln(5)

  def footer(self):
    self.set_y(-15)
    self.set_font('Arial', 'I', 8)
    self.cell(0, 10, f'Página {self.page_no()}', align='C')


def gerar_pdf_atendimento(
    cliente_nome, categoria, status, orcamento, fechado, descricao
):
  pdf = PDFRelatorio()
  pdf.add_page()

  pdf.set_font('Arial', 'B', 12)
  pdf.cell(0, 8, 'Detalhamento do Atendimento / Orçamento', ln=True)
  pdf.ln(3)

  pdf.set_font('Arial', '', 10)
  pdf.cell(0, 6, f'Cliente: {cliente_nome}', ln=True)
  pdf.cell(0, 6, f'Categoria: {categoria}', ln=True)
  pdf.cell(0, 6, f'Status: {status}', ln=True)
  pdf.cell(0, 6, f'Valor Orçado: R$ {orcamento:,.2f}', ln=True)
  pdf.cell(0, 6, f'Valor Fechado: R$ {fechado:,.2f}', ln=True)
  pdf.ln(4)

  pdf.set_font('Arial', 'B', 10)
  pdf.cell(0, 6, 'Descrição do Serviço:', ln=True)
  pdf.set_font('Arial', '', 10)
  pdf.multi_cell(
      0, 6, descricao if descricao else 'Sem descrição informada.'
  )

  return bytes(pdf.output())


def gerar_pdf_tabela(titulo, df):
  pdf = PDFRelatorio()
  pdf.add_page()

  pdf.set_font('Arial', 'B', 12)
  pdf.cell(0, 8, titulo, ln=True)
  pdf.ln(3)

  pdf.set_font('Arial', '', 9)
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
  return sqlite3.connect('gestao_escritorio.db')


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

  cursor.execute('SELECT COUNT(*) FROM usuarios')
  if cursor.fetchone()[0] == 0:
    senha_hash_padrao = gerar_hash_senha('conslin123')
    cursor.execute(
        """
        INSERT INTO usuarios (nome, usuario, senha_hash, perfil)
        VALUES (?, ?, ?, ?)
        """,
        ('Administrador Conslin', 'admin', senha_hash_padrao, 'Admin'),
    )

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

  cursor.execute('PRAGMA table_info(metas)')
  colunas_metas = [col[1] for col in cursor.fetchall()]
  if 'meta_diaria' not in colunas_metas:
    cursor.execute('ALTER TABLE metas ADD COLUMN meta_diaria REAL DEFAULT 0.0')
  if 'meta_semanal' not in colunas_metas:
    cursor.execute('ALTER TABLE metas ADD COLUMN meta_semanal REAL DEFAULT 0.0')

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

  categorias = [
      'Documentação',
      'Pequenos Serviços',
      'Reforma',
      'Manutenção',
      'Venda de Materiais',
  ]
  for cat in categorias:
    cursor.execute(
        'INSERT OR IGNORE INTO metas (categoria, meta_diaria, meta_semanal,'
        ' meta_valor) VALUES (?, 0.0, 0.0, 0.0)',
        (cat,),
    )

  conn.commit()
  conn.close()


# ==========================================
# AUTENTICAÇÃO E LOGIN
# ==========================================
def autenticar_usuario(usuario_input, senha_input):
  conn = conectar()
  cursor = conn.cursor()
  cursor.execute(
      'SELECT id, nome, usuario, senha_hash, perfil FROM usuarios WHERE'
      ' usuario = ?',
      (usuario_input.strip().lower(),),
  )
  res = cursor.fetchone()
  conn.close()

  if res:
    user_id, nome, user_login, hash_guardado, perfil = res
    if verificar_senha_hash(senha_input, hash_guardado):
      return {
          'id': user_id,
          'nome': nome,
          'usuario': user_login,
          'perfil': perfil,
      }
  return None


def tela_login():
  if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None

  if st.session_state['usuario_logado'] is None:
    st.title('🔒 Acesso Restrito - Conslin')
    with st.form('form_login'):
      usuario = st.text_input('Usuário').strip().lower()
      senha = st.text_input('Senha', type='password')
      btn_login = st.form_submit_button('Entrar')

      if btn_login:
        dados_user = autenticar_usuario(usuario, senha)
        if dados_user:
          st.session_state['usuario_logado'] = dados_user
          st.success(f"Bem-vindo(a), {dados_user['nome']}!")
          st.rerun()
        else:
          st.error('Usuário ou senha incorretos.')
    return False
  return True


# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
criar_tabelas()

st.set_page_config(page_title='Sistema de Gestão Conslin', layout='wide')

if tela_login():
  user = st.session_state['usuario_logado']
  perfil_usuario = user.get('perfil', 'Atendente')

  st.sidebar.markdown(
      f"👤 **{user['nome']}**  \n*(Perfil: **{perfil_usuario}**)*"
  )
  if st.sidebar.button('🚪 Sair / Logout'):
    st.session_state['usuario_logado'] = None
    st.rerun()

  CATEGORIAS = [
      'Documentação',
      'Pequenos Serviços',
      'Reforma',
      'Manutenção',
      'Venda de Materiais',
  ]
  STATUS_OPCOES = [
      'Primeiro Contato',
      'Em Orçamento',
      'Aprovado / Execução',
      'Concluído',
      'Cancelado',
  ]
  TIPOS_PARCEIROS = ['Prestador de Serviço', 'Equipe do Escritório', 'Fornecedor']
  TIPOS_CONTAS = [
      'Dívida',
      'Acordo',
      'Prestação de Serviço',
      'Fornecedor',
      'Equipe / Salário',
  ]

  st.title('🏗️ Conslin - Gestão Operacional & Financeira')

  menus_por_perfil = {
      'Atendente': [
          'Dashboard & Metas',
          'Projeção e Fluxo por Período',
          'Cadastro de Clientes',
          'Novo Atendimento / Orçamento',
          'Gestão de Atendimentos',
          'Contas e Parcelas a Receber',
      ],
      'Admin': [
          'Dashboard & Metas',
          'Projeção e Fluxo por Período',
          'Cadastro de Clientes',
          'Novo Atendimento / Orçamento',
          'Gestão de Atendimentos',
          'Contas e Parcelas a Receber',
          'Prestadores & Fornecedores',
          'Contas a Pagar, Dívidas & Acordos',
          'Registrar Pagamentos',
          'Fluxo de Caixa & DRE',
          '⚙️ Gerenciar Usuários',
      ],
  }

  opcoes_menu = menus_por_perfil.get(
      perfil_usuario, menus_por_perfil['Atendente']
  )
  menu = st.sidebar.radio('Navegação', opcoes_menu)

  # ----------------------------------------------------
  # DASHBOARD & METAS
  # ----------------------------------------------------
  if menu == 'Dashboard & Metas':
    st.header('🎯 Painel de Metas e Desempenho Temporal')

    conn = conectar()
    df_atendimentos = pd.read_sql_query('SELECT * FROM atendimentos', conn)
    df_metas = pd.read_sql_query('SELECT * FROM metas', conn)
    conn.close()

    if not df_atendimentos.empty:
      df_atendimentos['data_dt'] = pd.to_datetime(
          df_atendimentos['data_contato'], errors='coerce'
      ).dt.date
      df_aprovados = df_atendimentos[
          df_atendimentos['status'].isin(['Aprovado / Execução', 'Concluído'])
      ].copy()
    else:
      df_aprovados = pd.DataFrame(
          columns=['categoria', 'valor_fechado', 'data_dt']
      )

    hoje = date.today()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    inicio_mes = hoje.replace(day=1)
    inicio_ano = hoje.replace(month=1, day=1)

    if perfil_usuario == 'Admin':
      with st.expander(
          '⚙️ Configurar e Editar Metas (Diária, Semanal e Mensal) por Categoria'
      ):
        st.write(
            'Digite manualmente os valores de meta para cada categoria. Se a'
            ' meta diária ou semanal ainda não tiver sido salva, o sistema'
            ' trará uma sugestão inicial (semanal = mensal ÷ 4,33 | diária ='
            ' mensal ÷ 22 dias úteis de seg. a sex.).'
        )

        with st.form('form_metas_completas'):
          novas_metas_diarias = {}
          novas_metas_semanais = {}
          novas_metas_mensais = {}

          for cat in CATEGORIAS:
            st.markdown(f'**📍 Categoria: {cat}**')
            row_cat = (
                df_metas[df_metas['categoria'] == cat]
                if not df_metas.empty and cat in df_metas['categoria'].values
                else pd.DataFrame()
            )

            m_mensal_cad = (
                float(row_cat['meta_valor'].values[0])
                if not row_cat.empty and 'meta_valor' in row_cat.columns
                else 0.0
            )
            m_semanal_cad = (
                float(row_cat['meta_semanal'].values[0])
                if not row_cat.empty and 'meta_semanal' in row_cat.columns
                else 0.0
            )
            m_diaria_cad = (
                float(row_cat['meta_diaria'].values[0])
                if not row_cat.empty and 'meta_diaria' in row_cat.columns
                else 0.0
            )

            sugestao_semanal = (
                round(m_mensal_cad / 4.33, 2) if m_mensal_cad > 0 else 0.0
            )
            sugestao_diaria = (
                round(m_mensal_cad / 22.0, 2) if m_mensal_cad > 0 else 0.0
            )

            c1, c2, c3 = st.columns(3)
            val_m = c1.number_input(
                f'Meta Mensal ({cat})',
                value=m_mensal_cad,
                step=500.0,
                key=f'm_{cat}',
            )

            val_s_default = (
                m_semanal_cad if m_semanal_cad > 0 else sugestao_semanal
            )
            val_d_default = (
                m_diaria_cad if m_diaria_cad > 0 else sugestao_diaria
            )

            val_s = c2.number_input(
                f'Meta Semanal ({cat})',
                value=val_s_default,
                step=100.0,
                key=f's_{cat}',
                help='Livre para edição manual',
            )
            val_d = c3.number_input(
                f'Meta Diária ({cat})',
                value=val_d_default,
                step=50.0,
                key=f'd_{cat}',
                help='Livre para edição manual (segunda a sexta)',
            )

            novas_metas_mensais[cat] = val_m
            novas_metas_semanais[cat] = val_s
            novas_metas_diarias[cat] = val_d
            st.divider()

          if st.form_submit_button('💾 Salvar Todas as Metas'):
            conn = conectar()
            cursor = conn.cursor()
            for cat in CATEGORIAS:
              cursor.execute(
                  """
                                UPDATE metas 
                                SET meta_diaria = ?, meta_semanal = ?, meta_valor = ? 
                                WHERE categoria = ?
                                """,
                  (
                      novas_metas_diarias[cat],
                      novas_metas_semanais[cat],
                      novas_metas_mensais[cat],
                      cat,
                  ),
              )
            conn.commit()
            conn.close()
            st.success('Metas salvas e atualizadas com sucesso!')
            st.rerun()

    st.subheader('📊 Resumo Geral de Fechamentos x Metas Totais')

    val_hoje = (
        df_aprovados[df_aprovados['data_dt'] == hoje]['valor_fechado'].sum()
        if not df_aprovados.empty
        else 0.0
    )
    val_semana = (
        df_aprovados[df_aprovados['data_dt'] >= inicio_semana][
            'valor_fechado'
        ].sum()
        if not df_aprovados.empty
        else 0.0
    )
    val_mes = (
        df_aprovados[df_aprovados['data_dt'] >= inicio_mes][
            'valor_fechado'
        ].sum()
        if not df_aprovados.empty
        else 0.0
    )
    val_ano = (
        df_aprovados[df_aprovados['data_dt'] >= inicio_ano][
            'valor_fechado'
        ].sum()
        if not df_aprovados.empty
        else 0.0
    )

    meta_total_diaria = (
        df_metas['meta_diaria'].sum()
        if not df_metas.empty and 'meta_diaria' in df_metas.columns
        else 0.0
    )
    meta_total_semanal = (
        df_metas['meta_semanal'].sum()
        if not df_metas.empty and 'meta_semanal' in df_metas.columns
        else 0.0
    )
    meta_total_mensal = (
        df_metas['meta_valor'].sum() if not df_metas.empty else 0.0
    )

    col_d, col_s, col_m, col_a = st.columns(4)
    col_d.metric(
        'Vendas Hoje',
        f'R$ {val_hoje:,.2f}',
        delta=(
            f'{((val_hoje/meta_total_diaria)*100 if meta_total_diaria > 0 else 0):.1f}%'
            ' da meta'
            if meta_total_diaria > 0
            else 'Sem meta definida'
        ),
    )
    col_s.metric(
        'Vendas na Semana',
        f'R$ {val_semana:,.2f}',
        delta=(
            f'{((val_semana/meta_total_semanal)*100 if meta_total_semanal > 0 else 0):.1f}%'
            ' da meta'
            if meta_total_semanal > 0
            else 'Sem meta definida'
        ),
    )
    col_m.metric(
        'Vendas no Mês Atual',
        f'R$ {val_mes:,.2f}',
        delta=(
            f'{((val_mes/meta_total_mensal)*100 if meta_total_mensal > 0 else 0):.1f}%'
            ' da meta'
            if meta_total_mensal > 0
            else 'Sem meta definida'
        ),
    )
    col_a.metric('Acumulado do Ano', f'R$ {val_ano:,.2f}')

    st.divider()
    st.subheader('🎯 Atingimento de Metas por Categoria')

    visao_periodo = st.radio(
        'Selecione a meta que deseja comparar:',
        [
            'Meta Diária (Hoje)',
            'Meta Semanal (Semana Atual)',
            'Meta Mensal (Mês Vigente)',
        ],
        horizontal=True,
    )

    cols = st.columns(len(CATEGORIAS))
    for i, cat in enumerate(CATEGORIAS):
      row_cat = (
          df_metas[df_metas['categoria'] == cat]
          if not df_metas.empty and cat in df_metas['categoria'].values
          else pd.DataFrame()
      )

      if visao_periodo == 'Meta Diária (Hoje)':
        meta_val = (
            float(row_cat['meta_diaria'].values[0])
            if not row_cat.empty and 'meta_diaria' in row_cat.columns
            else 0.0
        )
        realizado_cat = (
            df_aprovados[
                (df_aprovados['categoria'] == cat)
                & (df_aprovados['data_dt'] == hoje)
            ]['valor_fechado'].sum()
            if not df_aprovados.empty
            else 0.0
        )
      elif visao_periodo == 'Meta Semanal (Semana Atual)':
        meta_val = (
            float(row_cat['meta_semanal'].values[0])
            if not row_cat.empty and 'meta_semanal' in row_cat.columns
            else 0.0
        )
        realizado_cat = (
            df_aprovados[
                (df_aprovados['categoria'] == cat)
                & (df_aprovados['data_dt'] >= inicio_semana)
            ]['valor_fechado'].sum()
            if not df_aprovados.empty
            else 0.0
        )
      else:
        meta_val = (
            float(row_cat['meta_valor'].values[0])
            if not row_cat.empty
            else 0.0
        )
        realizado_cat = (
            df_aprovados[
                (df_aprovados['categoria'] == cat)
                & (df_aprovados['data_dt'] >= inicio_mes)
            ]['valor_fechado'].sum()
            if not df_aprovados.empty
            else 0.0
        )

      percentual = (realizado_cat / meta_val * 100) if meta_val > 0 else 0.0
      with cols[i]:
        st.markdown(f'**{cat}**')
        st.metric(
            label='Realizado',
            value=f'R$ {realizado_cat:,.2f}',
            delta=f'{percentual:.1f}% de R$ {meta_val:,.2f}',
        )
        st.progress(min(percentual / 100, 1.0))

  # ----------------------------------------------------
  # PROJEÇÃO E FLUXO POR PERÍODO (NOVA FUNCIONALIDADE)
  # ----------------------------------------------------
  elif menu == 'Projeção e Fluxo por Período':
    st.header('📈 Previsão de Entradas, Despesas e Saldo Projetado')
    st.info(
        'Selecione a janela de tempo desejada para visualizar o dinheiro que'
        ' tem para entrar, os compromissos a pagar e o saldo final previsto.'
    )

    conn = conectar()
    df_rec = pd.read_sql_query(
        "SELECT * FROM contas_receber WHERE status = 'Pendente'", conn
    )
    df_pag = pd.read_sql_query(
        "SELECT * FROM contas_pagar WHERE status = 'Pendente'", conn
    )
    conn.close()

    hoje = date.today()
    fim_semana = hoje + timedelta(days=7)
    fim_mes = (hoje.replace(day=28) + timedelta(days=4)).replace(
        day=1
    ) - timedelta(days=1)

    opcao_periodo = st.radio(
        'Escolha a Visualização Temporal:',
        ['Visão do Dia (Hoje)', 'Visão da Semana (7 dias)', 'Visão do Mês'],
        horizontal=True,
    )

    # Tratamento de Datas das Contas a Receber
    if not df_rec.empty:
      df_rec['venc_dt'] = pd.to_datetime(
          df_rec['data_vencimento'], errors='coerce'
      ).dt.date
    else:
      df_rec = pd.DataFrame(
          columns=['descricao', 'valor', 'data_vencimento', 'venc_dt']
      )

    # Tratamento de Datas das Contas a Pagar
    if not df_pag.empty:
      df_pag['venc_dt'] = pd.to_datetime(
          df_pag['data_vencimento'], errors='coerce'
      ).dt.date
    else:
      df_pag = pd.DataFrame(
          columns=['descricao', 'valor', 'data_vencimento', 'venc_dt']
      )

    # Filtragem por Período
    if opcao_periodo == 'Visão do Dia (Hoje)':
      rec_filtrado = df_rec[df_rec['venc_dt'] == hoje]
      pag_filtrado = df_pag[df_pag['venc_dt'] == hoje]
      label_periodo = f'no dia {hoje.strftime("%d/%m/%Y")}'
    elif opcao_periodo == 'Visão da Semana (7 dias)':
      rec_filtrado = df_rec[
          (df_rec['venc_dt'] >= hoje) & (df_rec['venc_dt'] <= fim_semana)
      ]
      pag_filtrado = df_pag[
          (df_pag['venc_dt'] >= hoje) & (df_pag['venc_dt'] <= fim_semana)
      ]
      label_periodo = (
          f'de {hoje.strftime("%d/%m")} até {fim_semana.strftime("%d/%m/%Y")}'
      )
    else:
      rec_filtrado = df_rec[
          (df_rec['venc_dt'] >= hoje.replace(day=1))
          & (df_rec['venc_dt'] <= fim_mes)
      ]
      pag_filtrado = df_pag[
          (df_pag['venc_dt'] >= hoje.replace(day=1))
          & (df_pag['venc_dt'] <= fim_mes)
      ]
      label_periodo = f'no mês {hoje.strftime("%m/%Y")}'

    total_entradas = rec_filtrado['valor'].sum() if not rec_filtrado.empty else 0.0
    total_despesas = pag_filtrado['valor'].sum() if not pag_filtrado.empty else 0.0
    saldo_projetado = total_entradas - total_despesas

    st.subheader(f'💰 Resumo Financeiro {label_periodo}')

    m1, m2, m3 = st.columns(3)
    m1.metric('🟢 Dinheiro a Entrar', f'R$ {total_entradas:,.2f}')
    m2.metric('🔴 Despesas a Pagar', f'R$ {total_despesas:,.2f}')

    status_saldo = 'Positivo' if saldo_projetado >= 0 else 'Negativo'
    m3.metric(
        '📊 Saldo Projetado',
        f'R$ {saldo_projetado:,.2f}',
        delta=f'Saldo {status_saldo}',
        delta_color='normal' if saldo_projetado >= 0 else 'inverse',
    )

    if saldo_projetado < 0:
      st.error(
          f'⚠️ **Atenção:** O saldo projetado para este período está **NEGATIVO** em R$ {abs(saldo_projetado):,.2f}. As despesas superam as entradas previstass!'
      )
    else:
      st.success(
          f'✅ **Situação Regular:** O saldo projetado para este período está **POSITIVO** em R$ {saldo_projetado:,.2f}.'
      )

    st.divider()

    # Tabelas Detalhadas Lado a Lado
    col_t1, col_t2 = st.columns(2)

    with col_t1:
      st.markdown('### 📥 Entradas Previstas (A Receber)')
      if not rec_filtrado.empty:
        st.dataframe(
            rec_filtrado[['data_vencimento', 'descricao', 'valor']].rename(
                columns={
                    'data_vencimento': 'Vencimento',
                    'descricao': 'Descrição',
                    'valor': 'Valor (R$)',
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info('Nenhuma entrada prevista para este período.')

    with col_t2:
      st.markdown('### 📤 Despesas Previstas (A Pagar)')
      if not pag_filtrado.empty:
        st.dataframe(
            pag_filtrado[['data_vencimento', 'descricao', 'valor']].rename(
                columns={
                    'data_vencimento': 'Vencimento',
                    'descricao': 'Descrição',
                    'valor': 'Valor (R$)',
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info('Nenhuma despesa prevista para este período.')

  # ----------------------------------------------------
  # CADASTRO DE CLIENTES (COM EDIÇÃO E EXCLUSÃO)
  # ----------------------------------------------------
  elif menu == 'Cadastro de Clientes':
    st.header('👤 Cadastro e Gestão de Clientes')
    with st.form('form_cliente'):
      nome = st.text_input('Nome do Cliente / Razão Social *')
      telefone = st.text_input('Telefone / WhatsApp')
      email = st.text_input('E-mail')
      cpf_cnpj = st.text_input('CPF ou CNPJ')
      endereco = st.text_area('Endereço Completo')
      if st.form_submit_button('Cadastrar Cliente'):
        if nome:
          conn = conectar()
          cursor = conn.cursor()
          cursor.execute(
              'INSERT INTO clientes (nome, telefone, email, cpf_cnpj, endereco)'
              ' VALUES (?,?,?,?,?)',
              (nome, telefone, email, cpf_cnpj, endereco),
          )
          conn.commit()
          conn.close()
          st.success(f'Cliente {nome} cadastrado com sucesso!')
          st.rerun()
        else:
          st.error('O nome do cliente é obrigatório.')

    st.subheader('📋 Clientes Cadastrados')
    conn = conectar()
    df_cli = pd.read_sql_query('SELECT * FROM clientes', conn)
    conn.close()
    if not df_cli.empty:
      st.dataframe(df_cli, use_container_width=True)
    else:
      st.info('Nenhum cliente cadastrado até o momento.')
