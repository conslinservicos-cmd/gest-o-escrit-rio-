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


# ==========================================
# FUNÇÕES DE CRIPTOGRAFIA DE SENHA
# ==========================================
def gerar_hash_senha(senha):
  return hashlib.sha256(senha.encode('utf-8')).hexdigest()


def verificar_senha_hash(senha_digitada, hash_guardado):
  return gerar_hash_senha(senha_digitada) == hash_guardado


# ==========================================
# BANCO DE DADOS E MIGRAÇÕES
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
        horario TEXT DEFAULT '08:00',
        FOREIGN KEY (cliente_id) REFERENCES clientes (id)
    )
    """)

  cursor.execute("PRAGMA table_info(atendimentos)")
  colunas_atend = [col[1] for col in cursor.fetchall()]
  if 'horario' not in colunas_atend:
    cursor.execute("ALTER TABLE atendimentos ADD COLUMN horario TEXT DEFAULT '08:00'")

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
        status TEXT NOT NULL DEFAULT 'Pendente',
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

  # Tabela para a nova aba Navegação e Casa
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS navegacao_casa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        salario REAL DEFAULT 0.0,
        escritorio TEXT,
        armazenamento_casa TEXT
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
          'Atendimentos de Hoje',
          'Gestão de Atendimentos',
          'Navegação e Casa',
      ],
      'Admin': [
          'Dashboard & Metas',
          'Projeção e Fluxo por Período',
          'Cadastro de Clientes',
          'Novo Atendimento / Orçamento',
          'Atendimentos de Hoje',
          'Gestão de Atendimentos',
          'Prestadores & Fornecedores',
          'Contas a Pagar, Dívidas & Acordos',
          'Registrar Pagamentos',
          'Fluxo de Caixa & DRE',
          'Navegação e Casa',
          'Gerenciar Usuários',
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

    if perfil_usuario == 'Admin':
      with st.expander('⚙️ Configurar / Editar Metas por Categoria'):
        with st.form('form_metas'):
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

            m_m = (
                float(row_cat['meta_valor'].values[0])
                if not row_cat.empty and 'meta_valor' in row_cat.columns
                else 0.0
            )
            m_s = (
                float(row_cat['meta_semanal'].values[0])
                if not row_cat.empty and 'meta_semanal' in row_cat.columns
                else 0.0
            )
            m_d = (
                float(row_cat['meta_diaria'].values[0])
                if not row_cat.empty and 'meta_diaria' in row_cat.columns
                else 0.0
            )

            c1, c2, c3 = st.columns(3)
            val_m = c1.number_input(
                f'Meta Mensal ({cat})', value=m_m, step=500.0, key=f'm_{cat}'
            )
            val_s = c2.number_input(
                f'Meta Semanal ({cat})', value=m_s, step=100.0, key=f's_{cat}'
            )
            val_d = c3.number_input(
                f'Meta Diária ({cat})', value=m_d, step=50.0, key=f'd_{cat}'
            )

            novas_metas_mensais[cat] = val_m
            novas_metas_semanais[cat] = val_s
            novas_metas_diarias[cat] = val_d

          if st.form_submit_button('💾 Salvar Metas'):
            conn = conectar()
            cursor = conn.cursor()
            for cat in CATEGORIAS:
              cursor.execute(
                  """
                                INSERT INTO metas (categoria, meta_diaria, meta_semanal, meta_valor)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(categoria) DO UPDATE SET 
                                    meta_diaria = excluded.meta_diaria,
                                    meta_semanal = excluded.meta_semanal,
                                    meta_valor = excluded.meta_valor
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

    col_d, col_s, col_m = st.columns(3)
    col_d.metric('Vendas Hoje', f'R$ {val_hoje:,.2f}')
    col_s.metric('Vendas na Semana', f'R$ {val_semana:,.2f}')
    col_m.metric('Vendas no Mês', f'R$ {val_mes:,.2f}')

    st.divider()
    st.subheader('🎯 Atingimento Mensal por Categoria')
    cols = st.columns(len(CATEGORIAS))
    for i, cat in enumerate(CATEGORIAS):
      row_cat = (
          df_metas[df_metas['categoria'] == cat]
          if not df_metas.empty and cat in df_metas['categoria'].values
          else pd.DataFrame()
      )
      meta_val = (
          float(row_cat['meta_valor'].values[0]) if not row_cat.empty else 0.0
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
            label='Realizado Mês',
            value=f'R$ {realizado_cat:,.2f}',
            delta=f'{percentual:.1f}% de R$ {meta_val:,.2f}',
        )

  # ----------------------------------------------------
  # PROJEÇÃO E FLUXO POR PERÍODO
  # ----------------------------------------------------
  elif menu == 'Projeção e Fluxo por Período':
    st.header('📈 Previsão de Entradas, Despesas e Saldo Projetado')

    conn = conectar()
    df_atend = pd.read_sql_query('SELECT * FROM atendimentos', conn)
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

    if not df_atend.empty:
      df_atend['venc_dt'] = pd.to_datetime(
          df_atend['data_contato'], errors='coerce'
      ).dt.date
      rec_filtrado_base = df_atend[
          df_atend['status'].isin(['Aprovado / Execução', 'Concluído'])
      ].copy()
    else:
      rec_filtrado_base = pd.DataFrame(
          columns=['categoria', 'valor_fechado', 'data_contato', 'venc_dt']
      )

    if not df_pag.empty:
      df_pag['venc_dt'] = pd.to_datetime(
          df_pag['data_vencimento'], errors='coerce'
      ).dt.date
    else:
      df_pag = pd.DataFrame(
          columns=['descricao', 'valor', 'data_vencimento', 'venc_dt']
      )

    if opcao_periodo == 'Visão do Dia (Hoje)':
      rec_filtrado = rec_filtrado_base[rec_filtrado_base['venc_dt'] == hoje]
      pag_filtrado = df_pag[df_pag['venc_dt'] == hoje]
    elif opcao_periodo == 'Visão da Semana (7 dias)':
      rec_filtrado = rec_filtrado_base[
          (rec_filtrado_base['venc_dt'] >= hoje)
          & (rec_filtrado_base['venc_dt'] <= fim_semana)
      ]
      pag_filtrado = df_pag[
          (df_pag['venc_dt'] >= hoje) & (df_pag['venc_dt'] <= fim_semana)
      ]
    else:
      rec_filtrado = rec_filtrado_base[
          (rec_filtrado_base['venc_dt'] >= hoje.replace(day=1))
          & (rec_filtrado_base['venc_dt'] <= fim_mes)
      ]
      pag_filtrado = df_pag[
          (df_pag['venc_dt'] >= hoje.replace(day=1))
          & (df_pag['venc_dt'] <= fim_mes)
      ]

    total_entradas = (
        rec_filtrado['valor_fechado'].sum() if not rec_filtrado.empty else 0.0
    )
    total_despesas = pag_filtrado['valor'].sum() if not pag_filtrado.empty else 0.0
    saldo_projetado = total_entradas - total_despesas

    m1, m2, m3 = st.columns(3)
    m1.metric('🟢 Dinheiro a Entrar', f'R$ {total_entradas:,.2f}')
    m2.metric('🔴 Despesas a Pagar', f'R$ {total_despesas:,.2f}')
    m3.metric(
        '📊 Saldo Projetado',
        f'R$ {saldo_projetado:,.2f}',
        delta_color='normal' if saldo_projetado >= 0 else 'inverse',
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
      st.markdown('### 📥 Entradas Previstas (Atendimentos Fechados)')
      if not rec_filtrado.empty:
        st.dataframe(
            rec_filtrado[['data_contato', 'categoria', 'valor_fechado']].rename(
                columns={
                    'data_contato': 'Data',
                    'categoria': 'Categoria',
                    'valor_fechado': 'Valor (R$)',
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info('Nenhuma entrada prevista no período.')

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
        st.info('Nenhuma despesa no período.')

  # ----------------------------------------------------
  # CADASTRO DE CLIENTES
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

      st.divider()
      st.subheader('✏️ Editar ou 🗑️ Excluir Cliente')
      opcoes_cli = [
          f"ID {row['id']} - {row['nome']}" for _, row in df_cli.iterrows()
      ]
      cli_sel = st.selectbox('Selecione um Cliente', opcoes_cli)

      if cli_sel:
        id_cli = int(cli_sel.split(' ')[1])
        dados_cli = df_cli[df_cli['id'] == id_cli].iloc[0]

        tab_edit_cli, tab_del_cli = st.tabs(['✏️ Editar Dados', '🗑️ Excluir'])

        with tab_edit_cli:
          with st.form(f'form_edit_cli_{id_cli}'):
            edit_nome = st.text_input(
                'Nome / Razão Social', value=str(dados_cli['nome'])
            )
            edit_tel = st.text_input(
                'Telefone / WhatsApp', value=str(dados_cli['telefone'] or '')
            )
            edit_email = st.text_input(
                'E-mail', value=str(dados_cli['email'] or '')
            )
            edit_cpf = st.text_input(
                'CPF/CNPJ', value=str(dados_cli['cpf_cnpj'] or '')
            )
            edit_end = st.text_area(
                'Endereço', value=str(dados_cli['endereco'] or '')
            )

            if st.form_submit_button('💾 Salvar Alterações'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                UPDATE clientes 
                                SET nome = ?, telefone = ?, email = ?, cpf_cnpj = ?, endereco = ?
                                WHERE id = ?
                            """,
                  (
                      edit_nome,
                      edit_tel,
                      edit_email,
                      edit_cpf,
                      edit_end,
                      id_cli,
                  ),
              )
              conn.commit()
              conn.close()
              st.success('Cliente atualizado com sucesso!')
              st.rerun()

        with tab_del_cli:
          st.warning(
              '⚠️ Apagar este cliente pode afetar o histórico de atendimentos'
              ' vinculados.'
          )
          if st.button('🔥 Confirmar Exclusão do Cliente', key=f'del_cli_{id_cli}'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM clientes WHERE id = ?', (id_cli,))
            conn.commit()
            conn.close()
            st.success('Cliente excluído com sucesso!')
            st.rerun()
    else:
      st.info('Nenhum cliente cadastrado.')

  # ----------------------------------------------------
  # NOVO ATENDIMENTO / ORÇAMENTO
  # ----------------------------------------------------
  elif menu == 'Novo Atendimento / Orçamento':
    st.header('➕ Novo Atendimento ou Orçamento')

    conn = conectar()
    clientes = pd.read_sql_query('SELECT id, nome FROM clientes', conn)
    conn.close()

    if clientes.empty:
      st.warning('Cadastre pelo menos um cliente antes de criar atendimentos.')
    else:
      dict_clientes = dict(zip(clientes['nome'], clientes['id']))

      with st.form('form_atendimento'):
        cliente_sel = st.selectbox('Cliente', list(dict_clientes.keys()))
        categoria = st.selectbox('Categoria de Serviço', CATEGORIAS)
        status = st.selectbox('Status Inicial', STATUS_OPCOES)
        v_orc = st.number_input(
            'Valor Orçado (R$)', min_value=0.0, step=100.0, value=0.0
        )
        v_fec = st.number_input(
            'Valor Fechado (R$)', min_value=0.0, step=100.0, value=0.0
        )
        despesas = st.number_input(
            'Despesas/Custos Diretos (R$)', min_value=0.0, step=50.0, value=0.0
        )
        dt_contato = st.date_input('Data do Atendimento', date.today())
        hr_contato = st.text_input('Horário (Ex: 09:30)', value='09:00')
        desc = st.text_area('Descrição / Observações do Atendimento')

        if st.form_submit_button('💾 Salvar Atendimento'):
          c_id = dict_clientes[cliente_sel]
          conn = conectar()
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, data_contato, horario)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
              (
                  c_id,
                  categoria,
                  desc,
                  status,
                  v_orc,
                  v_fec,
                  despesas,
                  dt_contato,
                  hr_contato,
              ),
          )
          conn.commit()
          conn.close()
          st.success('Atendimento registrado com sucesso!')
          st.rerun()

  # ----------------------------------------------------
  # ATENDIMENTOS DE HOJE
  # ----------------------------------------------------
  elif menu == 'Atendimentos de Hoje':
    st.header(f'📅 Agenda de Hoje ({date.today().strftime("%d/%m/%Y")})')
    st.markdown('Organize seus compromissos, reuniões e serviços do dia abaixo.')

    conn = conectar()
    clientes = pd.read_sql_query('SELECT id, nome FROM clientes', conn)
    conn.close()

    with st.expander('➕ Adicionar Novo Compromisso / Atendimento para Hoje'):
      if clientes.empty:
        st.warning('Cadastre pelo menos um cliente na aba "Cadastro de Clientes" para vincular aqui.')
      else:
        dict_clientes_h = dict(zip(clientes['nome'], clientes['id']))
        with st.form('form_agenda_hoje'):
          c1, c2 = st.columns(2)
          h_cli = c1.selectbox('Cliente', list(dict_clientes_h.keys()), key='ag_cli')
          h_hora = c2.text_input('Horário (Ex: 14:00)', value='10:00', key='ag_hora')

          h_cat = st.selectbox('Categoria', CATEGORIAS, key='ag_cat')
          h_stat = st.selectbox('Status', STATUS_OPCOES, key='ag_stat')

          c3, c4 = st.columns(2)
          h_orc = c3.number_input('Valor Orçado (R$)', min_value=0.0, step=100.0, value=0.0, key='ag_orc')
          h_fec = c4.number_input('Valor Fechado (R$)', min_value=0.0, step=100.0, value=0.0, key='ag_fec')

          h_desc = st.text_area('Descrição / Detalhes do Compromisso', key='ag_desc')

          if st.form_submit_button('📅 Agendar na Agenda de Hoje'):
            cid_h = dict_clientes_h[h_cli]
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO atendimentos (cliente_id, categoria, descricao, status, valor_orcamento, valor_fechado, despesas, data_contato, horario)
                            VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?)
                        """,
                (cid_h, h_cat, h_desc, h_stat, h_orc, h_fec, date.today(), h_hora),
            )
            conn.commit()
            conn.close()
            st.success('Compromisso agendado com sucesso para hoje!')
            st.rerun()

    st.divider()
    st.subheader('📋 Seus Compromissos Agendados para Hoje')

    conn = conectar()
    query_hoje = f"""
            SELECT a.id, a.horario, c.nome as cliente, a.categoria, a.status, a.valor_fechado, a.descricao, a.cliente_id, a.valor_orcamento, a.despesas, a.data_contato
            FROM atendimentos a
            LEFT JOIN clientes c ON a.cliente_id = c.id
            WHERE a.data_contato = '{date.today()}'
            ORDER BY a.horario ASC
        """
    df_hoje = pd.read_sql_query(query_hoje, conn)
    conn.close()

    if not df_hoje.empty:
      st.dataframe(
          df_hoje[['horario', 'cliente', 'categoria', 'status', 'valor_fechado', 'descricao']].rename(
              columns={
                  'horario': 'Horário',
                  'cliente': 'Cliente',
                  'categoria': 'Categoria',
                  'status': 'Status',
                  'valor_fechado': 'Valor Fechado (R$)',
                  'descricao': 'Detalhes',
              }
          ),
          use_container_width=True,
          hide_index=True,
      )

      st.divider()
      st.subheader('✏️ Editar ou 🗑️ Excluir Compromisso da Agenda')

      opcoes_hoje = [
          f"ID {row['id']} - às {row['horario']} - {row['cliente']} ({row['categoria']})"
          for _, row in df_hoje.iterrows()
      ]
      atend_hoje_sel = st.selectbox('Selecione o Compromisso', opcoes_hoje)

      if atend_hoje_sel:
        id_h = int(atend_hoje_sel.split(' ')[1])
        dados_h = df_hoje[df_hoje['id'] == id_h].iloc[0]

        tab_edit_h, tab_pdf_h, tab_del_h = st.tabs(
            ['✏️ Editar Dados', '📄 Exportar PDF', '🗑️ Excluir']
        )

        with tab_edit_h:
          with st.form(f'edit_form_hoje_{id_h}'):
            hr_eh = st.text_input('Horário', value=str(dados_h['horario'] or '08:00'))
            cat_eh = st.selectbox(
                'Categoria',
                CATEGORIAS,
                index=CATEGORIAS.index(dados_h['categoria']) if dados_h['categoria'] in CATEGORIAS else 0,
            )
            stat_eh = st.selectbox(
                'Status',
                STATUS_OPCOES,
                index=STATUS_OPCOES.index(dados_h['status']) if dados_h['status'] in STATUS_OPCOES else 0,
            )
            orc_eh = st.number_input(
                'Valor Orçado', value=float(dados_h['valor_orcamento'])
            )
            fec_eh = st.number_input(
                'Valor Fechado', value=float(dados_h['valor_fechado'])
            )
            desc_eh = st.text_area(
                'Descrição', value=str(dados_h['descricao'] or '')
            )

            if st.form_submit_button('💾 Atualizar Compromisso'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                UPDATE atendimentos 
                                SET horario = ?, categoria = ?, status = ?, valor_orcamento = ?, valor_fechado = ?, descricao = ?
                                WHERE id = ?
                            """,
                  (
                      hr_eh,
                      cat_eh,
                      stat_eh,
                      orc_eh,
                      fec_eh,
                      desc_eh,
                      id_h,
                  ),
              )
              conn.commit()
              conn.close()
              st.success('Compromisso atualizado com sucesso!')
              st.rerun()

        with tab_pdf_h:
          pdf_bytes = gerar_pdf_atendimento(
              dados_h['cliente'],
              dados_h['categoria'],
              dados_h['status'],
              dados_h['valor_orcamento'],
              dados_h['valor_fechado'],
              dados_h['descricao'],
          )
          st.download_button(
              '📥 Baixar Relatório PDF',
              data=pdf_bytes,
              file_name=f'compromisso_hoje_{id_h}.pdf',
              mime='application/pdf',
              key=f'pdf_h_{id_h}',
          )

        with tab_del_h:
          st.warning(
              '⚠️ Tem certeza de que deseja apagar permanentemente este'
              ' compromisso?'
          )
          if st.button('🔥 Confirmar Exclusão', key=f'del_hoje_{id_h}'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM atendimentos WHERE id = ?', (id_h,)
            )
            conn.commit()
            conn.close()
            st.success('Compromisso excluído com sucesso!')
            st.rerun()
    else:
      st.info('Nenhum compromisso agendado para hoje. Utilize o formulário acima para adicionar o primeiro!')

  # ----------------------------------------------------
  # GESTÃO DE ATENDIMENTOS (GERAL)
  # ----------------------------------------------------
  elif menu == 'Gestão de Atendimentos':
    st.header('📋 Gestão e Edição de Atendimentos (Geral)')

    conn = conectar()
    query = """
            SELECT a.id, a.horario, c.nome as cliente, a.categoria, a.status, a.valor_orcamento, a.valor_fechado, a.despesas, a.data_contato, a.descricao, a.cliente_id
            FROM atendimentos a
            LEFT JOIN clientes c ON a.cliente_id = c.id
        """
    df_atend = pd.read_sql_query(query, conn)
    conn.close()

    if not df_atend.empty:
      st.dataframe(
          df_atend.drop(columns=['cliente_id']), use_container_width=True
      )

      st.divider()
      st.subheader('✏️ Editar ou 🗑️ Excluir Atendimento')

      opcoes_atend = [
          f"ID {row['id']} - {row['cliente']} ({row['categoria']})"
          for _, row in df_atend.iterrows()
      ]
      atend_sel = st.selectbox('Selecione um Atendimento', opcoes_atend)

      if atend_sel:
        id_atend = int(atend_sel.split(' ')[1])
        dados_atend = df_atend[df_atend['id'] == id_atend].iloc[0]

        tab_edit, tab_pdf, tab_del = st.tabs(
            ['✏️ Editar Dados', '📄 Exportar PDF', '🗑️ Excluir']
        )

        with tab_edit:
          with st.form(f'edit_form_{id_atend}'):
            hr_edit = st.text_input('Horário', value=str(dados_atend['horario'] or '08:00'))
            cat_edit = st.selectbox(
                'Categoria',
                CATEGORIAS,
                index=CATEGORIAS.index(dados_atend['categoria']),
            )
            stat_edit = st.selectbox(
                'Status',
                STATUS_OPCOES,
                index=STATUS_OPCOES.index(dados_atend['status']),
            )
            orc_edit = st.number_input(
                'Valor Orçado', value=float(dados_atend['valor_orcamento'])
            )
            fec_edit = st.number_input(
                'Valor Fechado', value=float(dados_atend['valor_fechado'])
            )
            desp_edit = st.number_input(
                'Despesas', value=float(dados_atend['despesas'])
            )
            desc_edit = st.text_area(
                'Descrição', value=str(dados_atend['descricao'] or '')
            )

            if st.form_submit_button('💾 Atualizar Atendimento'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                UPDATE atendimentos 
                                SET horario = ?, categoria = ?, status = ?, valor_orcamento = ?, valor_fechado = ?, despesas = ?, descricao = ?
                                WHERE id = ?
                            """,
                  (
                      hr_edit,
                      cat_edit,
                      stat_edit,
                      orc_edit,
                      fec_edit,
                      desp_edit,
                      desc_edit,
                      id_atend,
                  ),
              )
              conn.commit()
              conn.close()
              st.success('Atendimento atualizado com sucesso!')
              st.rerun()

        with tab_pdf:
          pdf_bytes = gerar_pdf_atendimento(
              dados_atend['cliente'],
              dados_atend['categoria'],
              dados_atend['status'],
              dados_atend['valor_orcamento'],
              dados_atend['valor_fechado'],
              dados_atend['descricao'],
          )
          st.download_button(
              '📥 Baixar Relatório PDF',
              data=pdf_bytes,
              file_name=f'atendimento_{id_atend}.pdf',
              mime='application/pdf',
          )

        with tab_del:
          st.warning(
              '⚠️ Tem certeza de que deseja apagar permanentemente este'
              ' registro?'
          )
          if st.button('🔥 Confirmar Exclusão', key=f'del_{id_atend}'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM atendimentos WHERE id = ?', (id_atend,)
            )
            conn.commit()
            conn.close()
            st.success('Registro excluído com sucesso!')
            st.rerun()
    else:
      st.info('Nenhum atendimento cadastrado.')

  # ----------------------------------------------------
  # PRESTADORES & FORNECEDORES
  # ----------------------------------------------------
  elif menu == 'Prestadores & Fornecedores':
    st.header('🤝 Gestão de Parceiros, Prestadores & Fornecedores')

    with st.form('form_parceiro'):
      p_nome = st.text_input('Nome do Parceiro / Empresa *')
      p_tipo = st.selectbox('Tipo de Parceiro', TIPOS_PARCEIROS)
      p_tel = st.text_input('Telefone')
      p_cpf = st.text_input('CPF ou CNPJ')
      p_pix = st.text_input('Chave PIX')
      p_obs = st.text_area('Observações / Especialidade')

      if st.form_submit_button('💾 Cadastrar Parceiro'):
        if p_nome:
          conn = conectar()
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO parceiros (nome, tipo, telefone, cpf_cnpj, chave_pix, observacao)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
              (p_nome, p_tipo, p_tel, p_cpf, p_pix, p_obs),
          )
          conn.commit()
          conn.close()
          st.success(f'Parceiro {p_nome} cadastrado com sucesso!')
          st.rerun()
        else:
          st.error('O nome do parceiro é obrigatório.')

    st.subheader('📋 Parceiros Cadastrados')
    conn = conectar()
    df_parc = pd.read_sql_query('SELECT * FROM parceiros', conn)
    conn.close()

    if not df_parc.empty:
      st.dataframe(df_parc, use_container_width=True)

      st.divider()
      st.subheader('✏️ Editar ou 🗑️ Excluir Parceiro')
      opcoes_parc = [
          f"ID {row['id']} - {row['nome']} ({row['tipo']})"
          for _, row in df_parc.iterrows()
      ]
      parc_sel = st.selectbox('Selecione um Parceiro', opcoes_parc)

      if parc_sel:
        id_parc = int(parc_sel.split(' ')[1])
        dados_parc = df_parc[df_parc['id'] == id_parc].iloc[0]

        tab_edit_p, tab_del_p = st.tabs(['✏️ Editar Dados', '🗑️ Excluir'])

        with tab_edit_p:
          with st.form(f'form_edit_parc_{id_parc}'):
            ep_nome = st.text_input('Nome', value=str(dados_parc['nome']))
            ep_tipo = st.selectbox(
                'Tipo',
                TIPOS_PARCEIROS,
                index=TIPOS_PARCEIROS.index(dados_parc['tipo'])
                if dados_parc['tipo'] in TIPOS_PARCEIROS
                else 0,
            )
            ep_tel = st.text_input(
                'Telefone', value=str(dados_parc['telefone'] or '')
            )
            ep_cpf = st.text_input(
                'CPF/CNPJ', value=str(dados_parc['cpf_cnpj'] or '')
            )
            ep_pix = st.text_input(
                'Chave PIX', value=str(dados_parc['chave_pix'] or '')
            )
            ep_obs = st.text_area(
                'Observações', value=str(dados_parc['observacao'] or '')
            )

            if st.form_submit_button('💾 Salvar Alterações'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                UPDATE parceiros
                                SET nome = ?, tipo = ?, telefone = ?, cpf_cnpj = ?, chave_pix = ?, observacao = ?
                                WHERE id = ?
                            """,
                  (ep_nome, ep_tipo, ep_tel, ep_cpf, ep_pix, ep_obs, id_parc),
              )
              conn.commit()
              conn.close()
              st.success('Parceiro atualizado com sucesso!')
              st.rerun()

        with tab_del_p:
          st.warning('⚠️ Apagar este parceiro excluirá o cadastro do sistema.')
          if st.button('🔥 Confirmar Exclusão', key=f'del_parc_{id_parc}'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM parceiros WHERE id = ?', (id_parc,))
            conn.commit()
            conn.close()
            st.success('Parceiro excluído com sucesso!')
            st.rerun()
    else:
      st.info('Nenhum parceiro cadastrado.')

  # ----------------------------------------------------
  # CONTAS A PAGAR, DÍVIDAS & ACORDOS
  # ----------------------------------------------------
  elif menu == 'Contas a Pagar, Dívidas & Acordos':
    st.header('📤 Lançamento de Contas a Pagar, Dívidas e Acordos')

    conn = conectar()
    parceiros = pd.read_sql_query('SELECT id, nome FROM parceiros', conn)
    conn.close()

    dict_parceiros = (
        dict(zip(parceiros['nome'], parceiros['id']))
        if not parceiros.empty
        else {}
    )

    with st.form('form_conta_pagar'):
      p_sel = st.selectbox(
          'Parceiro / Credor (Opcional)', ['Nenhum / Outro'] + list(dict_parceiros.keys())
      )
      tipo_c = st.selectbox('Tipo da Conta', TIPOS_CONTAS)
      desc = st.text_input('Descrição da Despesa / Acordo *')
      val = st.number_input('Valor Total (R$)', min_value=0.01, step=50.0)
      dt_venc = st.date_input('Data de Vencimento', date.today())

      if st.form_submit_button('💾 Lançar Despesa'):
        if desc and val > 0:
          parc_id = dict_parceiros.get(p_sel, None)
          conn = conectar()
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO contas_pagar (parceiro_id, descricao, tipo_conta, valor, data_vencimento, status)
                        VALUES (?, ?, ?, ?, ?, 'Pendente')
                    """,
              (parc_id, desc, tipo_c, val, dt_venc),
          )
          conn.commit()
          conn.close()
          st.success('Despesa cadastrada no Contas a Pagar!')
          st.rerun()
        else:
          st.error('Informe uma descrição e um valor válido.')

    st.subheader('📋 Contas Cadastradas')
    conn = conectar()
    df_cp = pd.read_sql_query(
        """
            SELECT cp.id, p.nome as parceiro, cp.tipo_conta, cp.descricao, cp.valor, cp.data_vencimento, cp.status, cp.parceiro_id
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
        """,
        conn,
    )
    conn.close()

    if not df_cp.empty:
      st.dataframe(
          df_cp.drop(columns=['parceiro_id']), use_container_width=True
      )

      st.divider()
      st.subheader('✏️ Editar ou 🗑️ Excluir Conta a Pagar')
      opcoes_cp = [
          f"ID {r['id']} - {r['descricao']} - R$ {r['valor']:,.2f} ({r['status']})"
          for _, r in df_cp.iterrows()
      ]
      cp_sel = st.selectbox('Selecione uma Conta para Modificar', opcoes_cp)

      if cp_sel:
        id_cp_mod = int(cp_sel.split(' ')[1])
        dados_cp = df_cp[df_cp['id'] == id_cp_mod].iloc[0]

        tab_edit_cp, tab_del_cp = st.tabs(['✏️ Editar Dados', '🗑️ Excluir'])

        with tab_edit_cp:
          with st.form(f'form_edit_cp_{id_cp_mod}'):
            ecp_desc = st.text_input(
                'Descrição', value=str(dados_cp['descricao'])
            )
            ecp_tipo = st.selectbox(
                'Tipo da Conta',
                TIPOS_CONTAS,
                index=TIPOS_CONTAS.index(dados_cp['tipo_conta'])
                if dados_cp['tipo_conta'] in TIPOS_CONTAS
                else 0,
            )
            ecp_val = st.number_input(
                'Valor (R$)', value=float(dados_cp['valor'])
            )
            ecp_venc = st.date_input(
                'Vencimento',
                datetime.strptime(
                    dados_cp['data_vencimento'], '%Y-%m-%d'
                ).date()
                if dados_cp['data_vencimento']
                else date.today(),
            )
            ecp_status = st.selectbox(
                'Status',
                ['Pendente', 'Pago'],
                index=0 if dados_cp['status'] == 'Pendente' else 1,
            )

            if st.form_submit_button('💾 Salvar Alterações'):
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                UPDATE contas_pagar
                                SET descricao = ?, tipo_conta = ?, valor = ?, data_vencimento = ?, status = ?
                                WHERE id = ?
                            """,
                  (
                      ecp_desc,
                      ecp_tipo,
                      ecp_val,
                      ecp_venc,
                      ecp_status,
                      id_cp_mod,
                  ),
              )
              conn.commit()
              conn.close()
              st.success('Conta a pagar atualizada com sucesso!')
              st.rerun()

        with tab_del_cp:
          st.warning(
              '⚠️ Deseja excluir este registro de conta a pagar?'
          )
          if st.button('🔥 Confirmar Exclusão', key=f'del_cp_{id_cp_mod}'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM contas_pagar WHERE id = ?', (id_cp_mod,)
            )
            conn.commit()
            conn.close()
            st.success('Conta excluída com sucesso!')
            st.rerun()
    else:
      st.info('Nenhuma conta a pagar cadastrada.')

  # ----------------------------------------------------
  # REGISTRAR PAGAMENTOS
  # ----------------------------------------------------
  elif menu == 'Registrar Pagamentos':
    st.header('💸 Quitar Despesas / Registrar Pagamentos')

    conn = conectar()
    df_cp = pd.read_sql_query(
        """
            SELECT cp.id, p.nome as parceiro, cp.descricao, cp.valor, cp.data_vencimento, cp.parceiro_id
            FROM contas_pagar cp
            LEFT JOIN parceiros p ON cp.parceiro_id = p.id
            WHERE cp.status = 'Pendente'
        """,
        conn,
    )
    conn.close()

    if not df_cp.empty:
      opcoes_pag = [
          f"ID {r['id']} - {r['descricao']} - R$ {r['valor']:,.2f} (Venc:"
          f" {r['data_vencimento']})"
          for _, r in df_cp.iterrows()
      ]
      conta_sel = st.selectbox('Selecione a Conta para Quitar', opcoes_pag)

      if conta_sel:
        id_cp = int(conta_sel.split(' ')[1])
        row_cp = df_cp[df_cp['id'] == id_cp].iloc[0]

        with st.form('form_quitar_pagamento'):
          val_pag = st.number_input(
              'Valor Pago (R$)', value=float(row_cp['valor'])
          )
          dt_pag = st.date_input('Data do Pagamento', date.today())
          forma = st.selectbox(
              'Forma de Pagamento', ['PIX', 'Transferência', 'Dinheiro', 'Boleto', 'Cartão']
          )
          comp = st.text_input('Comprovante / Ref. Transação')

          if st.form_submit_button('✅ Efetuar Baixa no Pagamento'):
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO pagamentos (conta_id, parceiro_id, valor_pago, data_pagamento, forma_pagamento, comprovante_ref)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """,
                (id_cp, row_cp['parceiro_id'], val_pag, dt_pag, forma, comp),
            )
            cursor.execute(
                "UPDATE contas_pagar SET status = 'Pago' WHERE id = ?", (id_cp,)
            )
            conn.commit()
            conn.close()
            st.success('Pagamento quitado com sucesso!')
            st.rerun()
    else:
      st.info('Não há contas pendentes de pagamento.')

  # ----------------------------------------------------
  # FLUXO DE CAIXA & DRE
  # ----------------------------------------------------
  elif menu == 'Fluxo de Caixa & DRE':
    st.header('📊 Fluxo de Caixa e DRE (Realizado)')

    conn = conectar()
    df_atend_pagos = pd.read_sql_query(
        "SELECT * FROM atendimentos WHERE status IN ('Aprovado / Execução',"
        " 'Concluído')",
        conn,
    )
    df_saidas = pd.read_sql_query('SELECT * FROM pagamentos', conn)
    conn.close()

    tot_entradas = (
        df_atend_pagos['valor_fechado'].sum()
        if not df_atend_pagos.empty
        else 0.0
    )
    tot_saidas = (
        df_saidas['valor_pago'].sum() if not df_saidas.empty else 0.0
    )
    lucro_liquido = tot_entradas - tot_saidas

    st.subheader('📌 Demonstrativo Geral')
    c1, c2, c3 = st.columns(3)
    c1.metric('🟢 Total Entradas (Atendimentos Fechados)', f'R$ {tot_entradas:,.2f}')
    c2.metric('🔴 Total Saídas Pagas', f'R$ {tot_saidas:,.2f}')
    c3.metric(
        '💵 Resultado Líquido',
        f'R$ {lucro_liquido:,.2f}',
        delta_color='normal' if lucro_liquido >= 0 else 'inverse',
    )

  # ----------------------------------------------------
  # NAVEGAÇÃO E CASA
  # ----------------------------------------------------
  elif menu == 'Navegação e Casa':
    st.header('🧭 Navegação e Casa')
    st.markdown('Gerencie as informações de salário, escritório e armazenamento da casa.')

    # Carrega dados salvos anteriormente se houver
    conn = conectar()
    df_nav = pd.read_sql_query('SELECT * FROM navegacao_casa', conn)
    conn.close()

    salario_atual = float(df_nav['salario'].iloc[-1]) if not df_nav.empty and 'salario' in df_nav.columns and len(df_nav) > 0 else 0.0
    escritorio_atual = str(df_nav['escritorio'].iloc[-1]) if not df_nav.empty and 'escritorio' in df_nav.columns and len(df_nav) > 0 and pd.notna(df_nav['escritorio'].iloc[-1]) else ''
    armazenamento_atual = str(df_nav['armazenamento_casa'].iloc[-1]) if not df_nav.empty and 'armazenamento_casa' in df_nav.columns and len(df_nav) > 0 and pd.notna(df_nav['armazenamento_casa'].iloc[-1]) else ''

    with st.form('form_navegacao_casa'):
      novo_salario = st.number_input('Salário (R$)', min_value=0.0, step=100.0, value=salario_atual)
      novo_escritorio = st.text_area('Escritório', value=escritorio_atual)
      novo_armazenamento = st.text_area('Armazenamento Casa', value=armazenamento_atual)

      if st.form_submit_button('💾 Salvar Informações'):
        conn = conectar()
        cursor = conn.cursor()
        # Salva um novo registro ou atualiza (aqui inserimos novo estado para histórico ou mantemos atualizado)
        cursor.execute(
            """
                INSERT INTO navegacao_casa (salario, escritorio, armazenamento_casa)
                VALUES (?, ?, ?)
            """,
            (novo_salario, novo_escritorio, novo_armazenamento),
        )
        conn.commit()
        conn.close()
        st.success('Informações de Navegação e Casa salvas com sucesso!')
        st.rerun()

    if not df_nav.empty:
      st.divider()
      st.subheader('📋 Histórico / Registros Salvos')
      st.dataframe(df_nav, use_container_width=True, hide_index=True)

  # ----------------------------------------------------
  # GERENCIAR USUÁRIOS
  # ----------------------------------------------------
  elif menu == 'Gerenciar Usuários':
    st.header('👥 Gestão de Usuários e Acessos ao Sistema')

    if perfil_usuario != 'Admin':
      st.error(
          'Acesso restrito apenas para administradores do sistema.'
      )
    else:
      with st.form('form_novo_usuario'):
        st.subheader('➕ Cadastrar Novo Usuário')
        u_nome = st.text_input('Nome Completo *')
        u_login = st.text_input('Nome de Usuário (login p/ entrar) *')
        u_senha = st.text_input('Senha Inicial *', type='password')
        u_perfil = st.selectbox('Perfil de Acesso', ['Atendente', 'Admin'])

        if st.form_submit_button('💾 Cadastrar Usuário'):
          if u_nome and u_login and u_senha:
            try:
              hash_s = gerar_hash_senha(u_senha)
              conn = conectar()
              cursor = conn.cursor()
              cursor.execute(
                  """
                                INSERT INTO usuarios (nome, usuario, senha_hash, perfil)
                                VALUES (?, ?, ?, ?)
                            """,
                  (u_nome, u_login.strip().lower(), hash_s, u_perfil),
              )
              conn.commit()
              conn.close()
              st.success(f'Usuário {u_nome} cadastrado com sucesso!')
              st.rerun()
            except sqlite3.IntegrityError:
              st.error(
                  'Este nome de usuário já existe. Escolha outro login.'
              )
          else:
            st.error('Preencha todos os campos obrigatórios (*).')

      st.divider()
      st.subheader('📋 Usuários Cadastrados no Sistema')
      conn = conectar()
      df_users = pd.read_sql_query(
          'SELECT id, nome, usuario, perfil FROM usuarios', conn
      )
      conn.close()

      if not df_users.empty:
        st.dataframe(df_users, use_container_width=True)

        st.divider()
        st.subheader('✏️ Editar ou 🗑️ Excluir Usuário')
        opcoes_u = [
            f"ID {r['id']} - {r['nome']} ({r['usuario']})"
            for _, r in df_users.iterrows()
        ]
        user_sel = st.selectbox('Selecione um Usuário', opcoes_u)

        if user_sel:
          id_u = int(user_sel.split(' ')[1])
          dados_u = df_users[df_users['id'] == id_u].iloc[0]

          tab_ed_u, tab_del_u = st.tabs(['✏️ Alterar Senha / Dados', '🗑️ Excluir'])

          with tab_ed_u:
            with st.form(f'form_edit_user_{id_u}'):
              eu_nome = st.text_input('Nome', value=str(dados_u['nome']))
              eu_login = st.text_input(
                  'Usuário (Login)', value=str(dados_u['usuario'])
              )
              eu_perfil = st.selectbox(
                  'Perfil',
                  ['Atendente', 'Admin'],
                  index=0 if dados_u['perfil'] == 'Atendente' else 1,
              )
              eu_nova_senha = st.text_input(
                  'Nova Senha (Deixe em branco para não alterar)',
                  type='password',
              )

              if st.form_submit_button('💾 Salvar Alterações'):
                conn = conectar()
                cursor = conn.cursor()
                if eu_nova_senha.strip():
                  novo_hash = gerar_hash_senha(eu_nova_senha)
                  cursor.execute(
                      """
                                        UPDATE usuarios 
                                        SET nome = ?, usuario = ?, perfil = ?, senha_hash = ? 
                                        WHERE id = ?
                                    """,
                      (
                          eu_nome,
                          eu_login.strip().lower(),
                          eu_perfil,
                          novo_hash,
                          id_u,
                      ),
                  )
                else:
                  cursor.execute(
                      """
                                        UPDATE usuarios 
                                        SET nome = ?, usuario = ?, perfil = ? 
                                        WHERE id = ?
                                    """,
                      (
                          eu_nome,
                          eu_login.strip().lower(),
                          eu_perfil,
                          id_u,
                      ),
                  )
                conn.commit()
                conn.close()
                st.success('Usuário atualizado com sucesso!')
                st.rerun()

          with tab_del_u:
            st.warning(
                '⚠️ Tem certeza de que deseja apagar este usuário do sistema?'
            )
            if id_u == user.get('id'):
              st.error(
                  'Você não pode excluir o seu próprio usuário logado no'
                  ' momento.'
              )
            else:
              if st.button('🔥 Confirmar Exclusão', key=f'del_u_{id_u}'):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM usuarios WHERE id = ?', (id_u,))
                conn.commit()
                conn.close()
                st.success('Usuário excluído com sucesso!')
                st.rerun()
