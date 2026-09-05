import sqlite3

def conectar():
    return sqlite3.connect("gestao_escritorio.db")

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()
    
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
    
    categorias = ["Documentação", "Pequenos Serviços", "Reforma", "Manutenção", "Venda de Materiais"]
    for cat in categorias:
        cursor.execute("INSERT OR IGNORE INTO metas (categoria, meta_valor) VALUES (?, 0.0)", (cat,))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_tabelas()
