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
          'Cadastro de Clientes',
          'Novo Atendimento / Orçamento',
          'Gestão de Atendimentos',
          'Contas e Parcelas a Receber',
      ],
      'Admin': [
          'Dashboard & Metas',
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
          st.error('O campo Nome é obrigatório.')

    st.subheader('Base de Clientes Cadastrados')
    conn = conectar()
    df_clientes = pd.read_sql_query('SELECT * FROM clientes', conn)
    conn.close()
    st.dataframe(df_clientes, use_container_width=True)

    if not df_clientes.empty:
      st.divider()
      st.subheader('✏️ Editar / 🗑️ Excluir Cliente')
      cliente_sel_id = st.selectbox(
          'Selecione o Cliente para Gerenciar:',
          options=df_clientes['id'].tolist(),
          format_func=lambda x: (
              f"ID {x} - "
              f" {df_clientes[df_clientes['id'] == x]['nome'].values[0]}"
          ),
      )

      cli_data = df_clientes[df_clientes['id'] == cliente_sel_id].iloc[0]

      col_ed, col_ex = st.columns(2)

      with col_ed:
        with st.expander('✏️ Editar Dados do Cliente'):
          with st.form('form_edita_cliente'):
            ed_nome = st.text_input('Nome', value=cli_data['nome'])
            ed_tel = st.text_input('Telefone', value=cli_data['telefone'] or '')
            ed_email = st.text_input('E-mail', value=cli_data['email'] or '')
            ed_cpf = st.text_input(
                'CPF/CNPJ', value=cli_data['cpf_cnpj'] or ''
            )
            ed_end = st.text_area('Endereço', value=cli_data['endereco'] or '')

            if st.form_submit_button('Salvar Alterações'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                UPDATE clientes 
                                SET nome=?, telefone=?, email=?, cpf_cnpj=?, endereco=?
                                WHERE id=?
                                """,
                  (ed_nome, ed_tel, ed_email, ed_cpf, ed_end, cliente_sel_id),
              )
              conn.commit()
              conn.close()
              st.success('Cliente atualizado com sucesso!')
              st.rerun()

      with col_ex:
        with st.expander('🗑️ Excluir Cliente'):
          st.warning(
              f'Tem certeza que deseja excluir o cliente #{cliente_sel_id} -'
              f" {cli_data['nome']}?"
          )
          if st.button('Confirmar Exclusão do Cliente', type='primary'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM clientes WHERE id = ?', (cliente_sel_id,)
            )
            conn.commit()
            conn.close()
            st.success('Cliente removido com sucesso!')
            st.rerun()

  # ----------------------------------------------------
  # NOVO ATENDIMENTO / ORÇAMENTO
  # ----------------------------------------------------
  elif menu == 'Novo Atendimento / Orçamento':
    st.header('📝 Registrar Novo Atendimento / Orçamento')
    conn = conectar()
    df_clientes = pd.read_sql_query('SELECT id, nome FROM clientes', conn)
    conn.close()

    if df_clientes.empty:
      st.warning('Nenhum cliente cadastrado. Cadastre um cliente primeiro.')
    else:
      opcoes_clientes = {
          f"{row['nome']} (ID: {row['id']})": row['id']
          for _, row in df_clientes.iterrows()
      }
      with st.form('form_atendimento'):
        cliente_sel = st.selectbox(
            'Selecione o Cliente', list(opcoes_clientes.keys())
        )
        categoria = st.selectbox('Categoria do Serviço', CATEGORIAS)
        status = st.selectbox('Status Inicial', STATUS_OPCOES, index=0)
        descricao = st.text_area('Descrição do Serviço / Necessidade')
        valor_orcamento = st.number_input(
            'Valor Estimado / Orçamento (R$)', value=0.0, step=100.0
        )
        valor_fechado = st.number_input(
            'Valor Fechado / Venda (R$)', value=0.0, step=100.0
        )
        despesas = st.number_input(
            'Despesas Previstas (R$)', value=0.0, step=50.0
        )
        data_contato = st.date_input(
            'Data do Fechamento / Contato', value=date.today()
        )

        gerar_recebivel = st.checkbox(
            'Gerar automaticamente lançamento de Conta a Receber (vencimento'
            ' hoje)',
            value=True,
        )

        if st.form_submit_button('Salvar Atendimento'):
          cliente_id = opcoes_clientes[cliente_sel]
          conn = conectar()
          cursor = conn.cursor()
          cursor.execute(
              """
                    INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, data_contato)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
              (
                  cliente_id,
                  categoria,
                  descricao,
                  status,
                  valor_orcamento,
                  valor_fechado,
                  despesas,
                  str(data_contato),
              ),
          )

          atendimento_id = cursor.lastrowid

          if (
              gerar_recebivel
              and status in ['Aprovado / Execução', 'Concluído']
              and valor_fechado > 0
          ):
            cursor.execute(
                """
                        INSERT INTO contas_receber (cliente_id, atendimento_id, descricao, valor, data_vencimento, status)
                        VALUES (?, ?, ?, ?, ?, 'Pendente')
                        """,
                (
                    cliente_id,
                    atendimento_id,
                    f'Fechamento - {categoria}',
                    valor_fechado,
                    str(data_contato),
                ),
            )

          conn.commit()
          conn.close()
          st.success('Atendimento registrado no banco de dados!')

  # ----------------------------------------------------
  # GESTÃO DE ATENDIMENTOS (EDIÇÃO E EXCLUSÃO)
  # ----------------------------------------------------
  elif menu == 'Gestão de Atendimentos':
    st.header('📋 Gestão e Atualização do Funil de Atendimentos')
    conn = conectar()
    query = """
        SELECT a.id, c.nome as Cliente, a.cliente_id, a.categoria as Categoria, a.status as Status, 
               a.valor_orcamento as [Orçado (R$)], a.valor_fechado as [Fechado (R$)], 
               a.despesas as [Despesas (R$)], a.descricao as Descrição, a.data_contato as Data
        FROM atendimentos a
        LEFT JOIN clientes c ON a.cliente_id = c.id
        """
    df_atendimentos = pd.read_sql_query(query, conn)
    df_clientes_all = pd.read_sql_query('SELECT id, nome FROM clientes', conn)
    conn.close()

    if df_atendimentos.empty:
      st.info('Nenhum atendimento registrado até o momento.')
    else:
      st.dataframe(
          df_atendimentos[[
              'id',
              'Cliente',
              'Categoria',
              'Status',
              'Orçado (R$)',
              'Fechado (R$)',
              'Data',
          ]],
          use_container_width=True,
      )

      pdf_bytes = gerar_pdf_tabela(
          'Relatorio de Atendimentos - Conslin',
          df_atendimentos[
              ['id', 'Cliente', 'Categoria', 'Status', 'Fechado (R$)']
          ],
      )
      st.download_button(
          '📄 Gerar PDF de Todos os Atendimentos',
          data=pdf_bytes,
          file_name='atendimentos_conslin.pdf',
          mime='application/pdf',
      )

      st.divider()
      st.subheader('✏️ Editar / 🗑️ Excluir / PDF Individual')
      atendimento_id = st.number_input(
          'Informe o ID do Atendimento', min_value=1, step=1
      )
      registro = df_atendimentos[df_atendimentos['id'] == atendimento_id]

      if not registro.empty:
        reg = registro.iloc[0]
        st.write(f"Atendimento selecionado: **Cliente: {reg['Cliente']}**")

        col_pdf, col_exc = st.columns(2)

        with col_pdf:
          pdf_ind = gerar_pdf_atendimento(
              reg['Cliente'],
              reg['Categoria'],
              reg['Status'],
              float(reg['Orçado (R$)']),
              float(reg['Fechado (R$)']),
              reg['Descrição'],
          )
          st.download_button(
              f"📥 Baixar PDF (ID #{reg['id']})",
              data=pdf_ind,
              file_name=f"orcamento_atendimento_{reg['id']}.pdf",
              mime='application/pdf',
          )

        with col_exc:
          if st.button(
              f"🗑️ Excluir Atendimento #{reg['id']}", type='primary'
          ):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM atendimentos WHERE id = ?', (atendimento_id,)
            )
            conn.commit()
            conn.close()
            st.success('Atendimento removido!')
            st.rerun()

        with st.form('form_edicao'):
          st.markdown('**Edição de Dados do Atendimento**')
          opcoes_cli_dict = {
              row['nome']: row['id'] for _, row in df_clientes_all.iterrows()
          }
          novo_cliente_nome = st.selectbox(
              'Cliente',
              list(opcoes_cli_dict.keys()),
              index=(
                  list(opcoes_cli_dict.keys()).index(reg['Cliente'])
                  if reg['Cliente'] in opcoes_cli_dict
                  else 0
              ),
          )
          nova_cat = st.selectbox(
              'Categoria',
              CATEGORIAS,
              index=(
                  CATEGORIAS.index(reg['Categoria'])
                  if reg['Categoria'] in CATEGORIAS
                  else 0
              ),
          )
          novo_status = st.selectbox(
              'Status',
              STATUS_OPCOES,
              index=(
                  STATUS_OPCOES.index(reg['Status'])
                  if reg['Status'] in STATUS_OPCOES
                  else 0
              ),
          )
          nova_desc = st.text_area(
              'Descrição do Serviço', value=reg['Descrição'] or ''
          )
          novo_orcamento = st.number_input(
              'Novo Valor Orçado (R$)', value=float(reg['Orçado (R$)'])
          )
          novo_fechado = st.number_input(
              'Novo Valor Fechado (R$)', value=float(reg['Fechado (R$)'])
          )
          novas_despesas = st.number_input(
              'Novas Despesas (R$)', value=float(reg['Despesas (R$)'])
          )

          gerar_receber_edicao = st.checkbox(
              'Lançar novo valor em Contas a Receber se aprovado/fechado',
              value=False,
          )

          if st.form_submit_button('Salvar Alterações no Atendimento'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                """
                                UPDATE atendimentos 
                                SET cliente_id = ?, categoria = ?, status = ?, descricao = ?, valor_orcamento = ?, valor_fechado = ?, despesas = ?
                                WHERE id = ?
                                """,
                (
                    opcoes_cli_dict[novo_cliente_nome],
                    nova_cat,
                    novo_status,
                    nova_desc,
                    novo_orcamento,
                    novo_fechado,
                    novas_despesas,
                    atendimento_id,
                ),
            )

            if (
                gerar_receber_edicao
                and novo_status in ['Aprovado / Execução', 'Concluído']
                and novo_fechado > 0
            ):
              cursor.execute(
                  """
                                INSERT INTO contas_receber (cliente_id, atendimento_id, descricao, valor, data_vencimento, status)
                                VALUES (?, ?, ?, ?, ?, 'Pendente')
                                """,
                  (
                      opcoes_cli_dict[novo_cliente_nome],
                      atendimento_id,
                      f'Ajuste Fechamento - {nova_cat}',
                      novo_fechado,
                      str(date.today()),
                  ),
              )

            conn.commit()
            conn.close()
            st.success('Registro atualizado com sucesso!')
            st.rerun()

  # ----------------------------------------------------
  # CONTAS E PARCELAS A RECEBER (COM EDIÇÃO E EXCLUSÃO)
  # ----------------------------------------------------
  elif menu == 'Contas e Parcelas a Receber':
    st.header('💵 Lançamento e Controle de Contas a Receber')

    conn = conectar()
    df_clientes = pd.read_sql_query('SELECT id, nome FROM clientes', conn)
    conn.close()

    if df_clientes.empty:
      st.warning(
          'Cadastre primeiro um cliente para registrar contas a receber.'
      )
    else:
      opcoes_clientes = {
          f"{row['nome']} (ID: {row['id']})": row['id']
          for _, row in df_clientes.iterrows()
      }

      with st.expander('➕ Lançar Nova Conta ou Parcela a Receber'):
        with st.form('form_contas_receber'):
          cliente_sel = st.selectbox(
              'Selecione o Cliente', list(opcoes_clientes.keys())
          )
          descricao = st.text_input(
              'Descrição (ex: Parcela 1/3 Reforma, Medição de Serviços,'
              ' Honorários)'
          )
          valor = st.number_input(
              'Valor a Receber (R$)', min_value=0.01, step=100.0
          )
          data_vencimento = st.date_input(
              'Data de Vencimento Prevista', value=date.today()
          )
          status_rec = st.selectbox('Status', ['Pendente', 'Recebido'])

          if st.form_submit_button('Lançar Valor a Receber'):
            cliente_id = opcoes_clientes[cliente_sel]
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                """
                                INSERT INTO contas_receber (cliente_id, descricao, valor, data_vencimento, status)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                (
                    cliente_id,
                    descricao,
                    valor,
                    str(data_vencimento),
                    status_rec,
                ),
            )
            conn.commit()
            conn.close()
            st.success('Previsão de recebimento gravada com sucesso!')
            st.rerun()

      st.subheader('📋 Lista de Recebimentos Previstos e Efetuados')
      conn = conectar()
      query_rec = """
            SELECT cr.id, c.nome as Cliente, cr.cliente_id, cr.descricao as Descrição, cr.valor as [Valor (R$)], 
                   cr.data_vencimento as [Vencimento], cr.status as Status
            FROM contas_receber cr
            LEFT JOIN clientes c ON cr.cliente_id = c.id
            ORDER BY cr.data_vencimento ASC
            """
      df_rec = pd.read_sql_query(query_rec, conn)
      conn.close()

      if not df_rec.empty:
        st.dataframe(
            df_rec[[
                'id',
                'Cliente',
                'Descrição',
                'Valor (R$)',
                'Vencimento',
                'Status',
            ]],
            use_container_width=True,
        )

        st.divider()
        st.subheader('✏️ Editar / 🗑️ Excluir / Confirmar Recebimento')

        rec_sel_id = st.selectbox(
            'Selecione o Lançamento para Alterar/Excluir:',
            df_rec['id'].tolist(),
        )
        row_rec = df_rec[df_rec['id'] == rec_sel_id].iloc[0]

        c_baixa, c_edit, c_del = st.columns(3)

        with c_baixa:
          if row_rec['Status'] == 'Pendente':
            if st.button('✅ Marcar como Recebido'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  "UPDATE contas_receber SET status = 'Recebido' WHERE id = ?",
                  (rec_sel_id,),
              )
              conn.commit()
              conn.close()
              st.success(f'Recebimento #{rec_sel_id} confirmado!')
              st.rerun()

        with c_edit:
          with st.expander('✏️ Editar Lançamento'):
            with st.form('form_edit_recebivel'):
              e_desc = st.text_input('Descrição', value=row_rec['Descrição'])
              e_val = st.number_input(
                  'Valor (R$)', value=float(row_rec['Valor (R$)'])
              )
              e_venc = st.date_input(
                  'Vencimento',
                  value=datetime.strptime(
                      row_rec['Vencimento'], '%Y-%m-%d'
                  ).date(),
              )
              e_stat = st.selectbox(
                  'Status',
                  ['Pendente', 'Recebido'],
                  index=0 if row_rec['Status'] == 'Pendente' else 1,
              )

              if st.form_submit_button('Salvar Alterações'):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute(
                    """
                                    UPDATE contas_receber 
                                    SET descricao=?, valor=?, data_vencimento=?, status=?
                                    WHERE id=?
                                    """,
                    (e_desc, e_val, str(e_venc), e_stat, rec_sel_id),
                )
                conn.commit()
                conn.close()
                st.success('Lançamento atualizado!')
                st.rerun()

        with c_del:
          with st.expander('🗑️ Excluir Lançamento'):
            if st.button('Confirmar Exclusão', type='primary'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  'DELETE FROM contas_receber WHERE id = ?', (rec_sel_id,)
              )
              conn.commit()
              conn.close()
              st.success('Lançamento excluído com sucesso!')
              st.rerun()

  # ----------------------------------------------------
  # PRESTADORES, EQUIPE E FORNECEDORES (ADMIN) (EDIÇÃO E EXCLUSÃO)
  # ----------------------------------------------------
  elif menu == 'Prestadores & Fornecedores':
    if perfil_usuario != 'Admin':
      st.error('🚫 Acesso não autorizado para o seu perfil.')
    else:
      st.header('👷 Cadastrar Prestadores, Equipe e Fornecedores')
      with st.form('form_parceiro'):
        nome = st.text_input('Nome / Razão Social *')
        tipo = st.selectbox('Tipo de Cadastro', TIPOS_PARCEIROS)
        telefone = st.text_input('Telefone / WhatsApp')
        cpf_cnpj = st.text_input('CPF ou CNPJ')
        chave_pix = st.text_input('Chave PIX / Dados Bancários')
        observacao = st.text_area(
            'Observações (Especialidade, Condições, etc.)'
        )
        if st.form_submit_button('Cadastrar'):
          if nome:
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                """
                                INSERT INTO parceiros (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao),
            )
            conn.commit()
            conn.close()
            st.success(f"{tipo} '{nome}' cadastrado com sucesso!")
            st.rerun()
          else:
            st.error('O campo Nome é obrigatório.')

      st.subheader('Lista de Prestadores, Equipe e Fornecedores')
      conn = conectar()
      df_parceiros = pd.read_sql_query('SELECT * FROM parceiros', conn)
      conn.close()
      st.dataframe(df_parceiros, use_container_width=True)

      if not df_parceiros.empty:
        st.divider()
        st.subheader('✏️ Editar / 🗑️ Excluir Cadastro de Parceiro')
        parc_sel_id = st.selectbox(
            'Selecione o Parceiro:',
            options=df_parceiros['id'].tolist(),
            format_func=lambda x: (
                f"ID {x} - "
                f" {df_parceiros[df_parceiros['id'] == x]['nome'].values[0]}"
            ),
        )

        p_row = df_parceiros[df_parceiros['id'] == parc_sel_id].iloc[0]

        cp_ed, cp_del = st.columns(2)

        with cp_ed:
          with st.expander('✏️ Editar Parceiro'):
            with st.form('form_edit_parceiro'):
              e_nome = st.text_input('Nome', value=p_row['nome'])
              e_tipo = st.selectbox(
                  'Tipo',
                  TIPOS_PARCEIROS,
                  index=(
                      TIPOS_PARCEIROS.index(p_row['tipo'])
                      if p_row['tipo'] in TIPOS_PARCEIROS
                      else 0
                  ),
              )
              e_tel = st.text_input('Telefone', value=p_row['telefone'] or '')
              e_cpf = st.text_input('CPF/CNPJ', value=p_row['cpf_cnpj'] or '')
              e_pix = st.text_input('Chave PIX', value=p_row['chave_pix'] or '')
              e_obs = st.text_area(
                  'Observação', value=p_row['observacao'] or ''
              )

              if st.form_submit_button('Salvar Alterações'):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute(
                    """
                                    UPDATE parceiros 
                                    SET nome=?, tipo=?, telefone=?, cpf_cnpj=?, chave_pix=?, observacao=?
                                    WHERE id=?
                                    """,
                    (
                        e_nome,
                        e_tipo,
                        e_tel,
                        e_cpf,
                        e_pix,
                        e_obs,
                        parc_sel_id,
                    ),
                )
                conn.commit()
                conn.close()
                st.success('Cadastro atualizado!')
                st.rerun()

        with cp_del:
          with st.expander('🗑️ Excluir Parceiro'):
            st.warning(f"Excluir '{p_row['nome']}'?")
            if st.button('Confirmar Exclusão', type='primary'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  'DELETE FROM parceiros WHERE id = ?', (parc_sel_id,)
              )
              conn.commit()
              conn.close()
              st.success('Parceiro removido!')
              st.rerun()

  # ----------------------------------------------------
  # CONTAS A PAGAR (ADMIN) (EDIÇÃO E EXCLUSÃO)
  # ----------------------------------------------------
  elif menu == 'Contas a Pagar, Dívidas & Acordos':
    if perfil_usuario != 'Admin':
      st.error('🚫 Acesso não autorizado para o seu perfil.')
    else:
      st.header('💸 Contas a Pagar, Dívidas e Acordos')
      conn = conectar()
      df_parceiros = pd.read_sql_query(
          'SELECT id, nome, tipo FROM parceiros', conn
      )
      conn.close()

      if df_parceiros.empty:
        st.warning(
            'Cadastre primeiro um prestador ou fornecedor na aba '
            "'Prestadores & Fornecedores'."
        )
      else:
        opcoes_parceiros = {
            f"{row['nome']} ({row['tipo']})": row['id']
            for _, row in df_parceiros.iterrows()
        }

        with st.expander('➕ Lançar Nova Conta a Pagar / Dívida / Acordo'):
          with st.form('form_conta_pagar'):
            parceiro_sel = st.selectbox(
                'Favorecido / Credor', list(opcoes_parceiros.keys())
            )
            tipo_conta = st.selectbox('Tipo de Conta', TIPOS_CONTAS)
            descricao = st.text_input('Descrição da Despesa / Objeto do Acordo')
            valor = st.number_input('Valor Total (R$)', min_value=0.01, step=100.0)
            data_vencimento = st.date_input('Data de Vencimento', value=date.today())
            status = st.selectbox('Status', ['Pendente', 'Pago', 'Parcial'])

            if st.form_submit_button('Lançar Conta'):
              parceiro_id = opcoes_parceiros[parceiro_sel]
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                INSERT INTO contas_pagar (parceiro_id, descricao, tipo_conta, valor, data_vencimento, status)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                  (
                      parceiro_id,
                      descricao,
                      tipo_conta,
                      valor,
                      str(data_vencimento),
                      status,
                  ),
              )
              conn.commit()
              conn.close()
              st.success('Conta a pagar registrada com sucesso!')
              st.rerun()

        st.subheader('📋 Contas Cadastradas a Pagar')
        conn = conectar()
        query_cp = """
                SELECT cp.id, p.nome as Favorecido, cp.parceiro_id, cp.tipo_conta as Tipo, cp.descricao as Descrição, 
                       cp.valor as [Valor (R$)], cp.data_vencimento as [Vencimento], cp.status as Status
                FROM contas_pagar cp
                LEFT JOIN parceiros p ON cp.parceiro_id = p.id
                ORDER BY cp.data_vencimento ASC
                """
        df_cp = pd.read_sql_query(query_cp, conn)
        conn.close()
        st.dataframe(
            df_cp[[
                'id',
                'Favorecido',
                'Tipo',
                'Descrição',
                'Valor (R$)',
                'Vencimento',
                'Status',
            ]],
            use_container_width=True,
        )

        if not df_cp.empty:
          st.divider()
          st.subheader('✏️ Editar / 🗑️ Excluir Conta a Pagar')

          cp_sel_id = st.selectbox('Selecione a Conta:', df_cp['id'].tolist())
          row_cp = df_cp[df_cp['id'] == cp_sel_id].iloc[0]

          c_cp_ed, c_cp_del = st.columns(2)

          with c_cp_ed:
            with st.expander('✏️ Editar Conta'):
              with st.form('form_edit_cp'):
                e_desc = st.text_input('Descrição', value=row_cp['Descrição'])
                e_tipo = st.selectbox(
                    'Tipo',
                    TIPOS_CONTAS,
                    index=(
                        TIPOS_CONTAS.index(row_cp['Tipo'])
                        if row_cp['Tipo'] in TIPOS_CONTAS
                        else 0
                    ),
                )
                e_val = st.number_input(
                    'Valor (R$)', value=float(row_cp['Valor (R$)'])
                )
                e_venc = st.date_input(
                    'Vencimento',
                    value=datetime.strptime(
                        row_cp['Vencimento'], '%Y-%m-%d'
                    ).date(),
                )
                e_stat = st.selectbox(
                    'Status',
                    ['Pendente', 'Pago', 'Parcial'],
                    index=(
                        ['Pendente', 'Pago', 'Parcial'].index(row_cp['Status'])
                        if row_cp['Status'] in ['Pendente', 'Pago', 'Parcial']
                        else 0
                    ),
                )

                if st.form_submit_button('Salvar Alterações'):
                  conn = conectar()
                  cursor = conn.cursor()
                  cursor.execute(
                      """
                                      UPDATE contas_pagar 
                                      SET descricao=?, tipo_conta=?, valor=?, data_vencimento=?, status=?
                                      WHERE id=?
                                      """,
                      (e_desc, e_tipo, e_val, str(e_venc), e_stat, cp_sel_id),
                  )
                  conn.commit()
                  conn.close()
                  st.success('Conta atualizada!')
                  st.rerun()

          with c_cp_del:
            with st.expander('🗑️ Excluir Conta'):
              if st.button('Confirmar Exclusão de Conta', type='primary'):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM contas_pagar WHERE id = ?', (cp_sel_id,)
                )
                conn.commit()
                conn.close()
                st.success('Conta excluída com sucesso!')
                st.rerun()

  # ----------------------------------------------------
  # REGISTRAR PAGAMENTOS (ADMIN)
  # ----------------------------------------------------
  elif menu == 'Registrar Pagamentos':
    if perfil_usuario != 'Admin':
      st.error('🚫 Acesso não autorizado para o seu perfil.')
    else:
      st.header('💳 Registrar Baixa e Pagamentos Efetuados')
      conn = conectar()
      query_pendentes = """
            SELECT cp.id, p.nome as Favorecido, cp.parceiro_id, cp.descricao, cp.valor, cp.status
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
            WHERE cp.status IN ('Pendente', 'Parcial')
            """
      df_pendentes = pd.read_sql_query(query_pendentes, conn)
      conn.close()

      if df_pendentes.empty:
        st.info('Nenhuma conta pendente ou parcial para quitar.')
      else:
        opcoes_contas = {
            f"ID #{row['id']} - {row['Favorecido']} - {row['descricao']} (R$"
            f" {row['valor']:,.2f})": row['id']
            for _, row in df_pendentes.iterrows()
        }

        with st.form('form_pagamento'):
          conta_sel = st.selectbox('Selecione a Conta', list(opcoes_contas.keys()))
          valor_pago = st.number_input('Valor Pago (R$)', min_value=0.01, step=50.0)
          data_pagamento = st.date_input('Data do Pagamento', value=date.today())
          forma_pagamento = st.selectbox(
              'Forma de Pagamento', ['PIX', 'Transferência', 'Boleto', 'Dinheiro']
          )
          comprovante_ref = st.text_input(
              'Comprovante / Autenticação / Ref. Código'
          )
          quitar_totalmente = st.checkbox(
              'Marcar conta como totalmente PAGA', value=True
          )

          if st.form_submit_button('Registrar Pagamento'):
            conta_id = opcoes_contas[conta_sel]
            row_conta = df_pendentes[df_pendentes['id'] == conta_id].iloc[0]
            parceiro_id = int(row_conta['parceiro_id'])

            conn = conectar()
            cursor = conn.cursor()

            cursor.execute(
                """
                            INSERT INTO pagamentos (conta_id, parceiro_id, valor_pago, data_pagamento, forma_pagamento, comprovante_ref)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                (
                    conta_id,
                    parceiro_id,
                    valor_pago,
                    str(data_pagamento),
                    forma_pagamento,
                    comprovante_ref,
                ),
            )

            novo_status = 'Pago' if quitar_totalmente else 'Parcial'
            cursor.execute(
                'UPDATE contas_pagar SET status = ? WHERE id = ?',
                (novo_status, conta_id),
            )

            conn.commit()
            conn.close()
            st.success('Pagamento registrado com sucesso!')
            st.rerun()

      st.subheader('📜 Histórico de Pagamentos Realizados')
      conn = conectar()
      query_hist = """
            SELECT pg.id, p.nome as Favorecido, cp.descricao as Conta, pg.valor_pago as [Valor Pago (R$)], 
                   pg.data_pagamento as [Data], pg.forma_pagamento as Forma, pg.comprovante_ref as [Comprovante Ref]
            FROM pagamentos pg
            LEFT JOIN parceiros p ON pg.parceiro_id = p.id
            LEFT JOIN contas_pagar cp ON pg.conta_id = cp.id
            ORDER BY pg.data_pagamento DESC
            """
      df_hist = pd.read_sql_query(query_hist, conn)
      conn.close()
      st.dataframe(df_hist, use_container_width=True)

  # ----------------------------------------------------
  # FLUXO DE CAIXA & DRE (ADMIN)
  # ----------------------------------------------------
  elif menu == 'Fluxo de Caixa & DRE':
    if perfil_usuario != 'Admin':
      st.error('🚫 Acesso não autorizado para o seu perfil.')
    else:
      st.header('📈 Fluxo de Caixa e Demonstrativo Financeiro (DRE)')

      conn = conectar()
      df_recebidos = pd.read_sql_query(
          "SELECT valor FROM contas_receber WHERE status = 'Recebido'", conn
      )
      df_atend_fechados = pd.read_sql_query(
          "SELECT valor_fechado, despesas FROM atendimentos WHERE status IN"
          " ('Aprovado / Execução', 'Concluído')",
          conn,
      )
      df_pagos = pd.read_sql_query('SELECT valor_pago FROM pagamentos', conn)
      conn.close()

      total_recebido_contas = (
          df_recebidos['valor'].sum() if not df_recebidos.empty else 0.0
      )
      total_vendas_fechadas = (
          df_atend_fechados['valor_fechado'].sum()
          if not df_atend_fechados.empty
          else 0.0
      )
      total_despesas_obra = (
          df_atend_fechados['despesas'].sum()
          if not df_atend_fechados.empty
          else 0.0
      )
      total_pagamentos_efetuados = (
          df_pagos['valor_pago'].sum() if not df_pagos.empty else 0.0
      )

      receita_bruta = max(total_recebido_contas, total_vendas_fechadas)
      total_custos_despesas = total_despesas_obra + total_pagamentos_efetuados
      resultado_liquido = receita_bruta - total_custos_despesas

      c1, c2, c3 = st.columns(3)
      c1.metric('Receita Total Realizada', f'R$ {receita_bruta:,.2f}')
      c2.metric(
          'Total Saídas / Custos / Despesas',
          f'R$ {total_custos_despesas:,.2f}',
      )
      c3.metric(
          'Resultado Líquido do Período',
          f'R$ {resultado_liquido:,.2f}',
          delta=f'R$ {resultado_liquido:,.2f}',
      )

      st.divider()
      st.subheader('📊 Resumo do DRE Simplificado')
      dre_data = {
          'Indicador': [
              '(+) Receita Operacional Bruta (Fechamentos/Recebimentos)',
              '(-) Custos Diretos de Obras / Serviços (Despesas de Atendimento)',
              '(-) Despesas Operacionais, Salários, Credores e Fornecedores',
              '(=) Resultado Líquido Final',
          ],
          'Valor (R$)': [
              receita_bruta,
              -total_despesas_obra,
              -total_pagamentos_efetuados,
              resultado_liquido,
          ],
      }
      df_dre = pd.DataFrame(dre_data)
      st.dataframe(df_dre, use_container_width=True)

  # ----------------------------------------------------
  # GERENCIAR USUÁRIOS (ADMIN)
  # ----------------------------------------------------
  elif menu == '⚙️ Gerenciar Usuários':
    if perfil_usuario != 'Admin':
      st.error('🚫 Acesso não autorizado para o seu perfil.')
    else:
      st.header('⚙️ Gerenciamento de Usuários e Permissões')

      with st.expander('➕ Cadastrar Novo Usuário'):
        with st.form('form_novo_usuario'):
          novo_nome = st.text_input('Nome Completo')
          novo_login = st.text_input('Nome de Usuário (Login)').strip().lower()
          nova_senha = st.text_input('Senha', type='password')
          novo_perfil = st.selectbox('Perfil de Acesso', ['Atendente', 'Admin'])

          if st.form_submit_button('Cadastrar Usuário'):
            if novo_nome and novo_login and nova_senha:
              conn = conectar()
              cursor = conn.cursor()
              try:
                hash_s = gerar_hash_senha(nova_senha)
                cursor.execute(
                    """
                                    INSERT INTO usuarios (nome, usuario, senha_hash, perfil)
                                    VALUES (?, ?, ?, ?)
                                    """,
                    (novo_nome, novo_login, hash_s, novo_perfil),
                )
                conn.commit()
                st.success(f"Usuário '{novo_login}' criado com sucesso!")
                st.rerun()
              except sqlite3.IntegrityError:
                st.error('O nome de usuário já existe. Escolha outro.')
              finally:
                conn.close()
            else:
              st.error('Preencha todos os campos.')

      st.subheader('👥 Usuários Cadastrados')
      conn = conectar()
      df_users = pd.read_sql_query(
          'SELECT id, nome, usuario, perfil FROM usuarios', conn
      )
      conn.close()
      st.dataframe(df_users, use_container_width=True)

      if not df_users.empty:
        st.divider()
        st.subheader('🗑️ Excluir Usuário')
        usr_sel_id = st.selectbox(
            'Selecione o Usuário para Remover:',
            df_users[df_users['usuario'] != 'admin']['id'].tolist(),
            format_func=lambda x: (
                f"ID {x} - "
                f" {df_users[df_users['id'] == x]['nome'].values[0]} "
                f"({df_users[df_users['id'] == x]['usuario'].values[0]})"
            ),
        )
        if st.button('Excluir Usuário Selecionado', type='primary'):
          conn = conectar()
          cursor = conn.cursor()
          cursor.execute('DELETE FROM usuarios WHERE id = ?', (usr_sel_id,))
          conn.commit()
          conn.close()
          st.success('Usuário removido!')
          st.rerun()
