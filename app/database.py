import os
import sqlite3
import configparser
import urllib.parse

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Arquivo de banco sqlite padrão (no root do projeto)
SQLITE_FILE = os.environ.get('SQLITE_FILE') or os.path.join(ROOT_DIR, 'financeiro.db')

# Detecta se há uma URL de banco de dados PostgreSQL configurada (prefere variáveis de ambiente)
DATABASE_URL = os.environ.get('DATABASE_URL')

# Se não houver env var, tenta ler um arquivo de configuração `config.ini` no root do projeto
config_path = os.path.join(ROOT_DIR, 'config.ini')
if not DATABASE_URL and os.path.exists(config_path):
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    if 'database' in cfg:
        dbcfg = cfg['database']
        # Se o usuário forneceu uma URL completa, usa ela
        if dbcfg.get('url'):
            DATABASE_URL = dbcfg.get('url')
        else:
            driver = dbcfg.get('driver', '').lower()
            if driver in ('postgres', 'postgresql') or dbcfg.get('host'):
                # Monta a URL do Postgres a partir dos campos
                user = dbcfg.get('user', '')
                pwd = dbcfg.get('password', '')
                host = dbcfg.get('host', 'localhost')
                port = dbcfg.get('port', '5432')
                dbname = dbcfg.get('dbname') or dbcfg.get('database') or ''
                if pwd:
                    pwd = urllib.parse.quote_plus(pwd)
                DATABASE_URL = f"postgresql://{user}:{pwd}@{host}:{port}/{dbname}"
            elif driver in ('sqlite', '') or dbcfg.get('file'):
                # Permite especificar arquivo sqlite no config
                SQLITE_FILE = dbcfg.get('file', SQLITE_FILE)

USE_POSTGRES = False
_psycopg2 = None

if DATABASE_URL and DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    try:
        import psycopg2
        import psycopg2.extras
        _psycopg2 = psycopg2
        USE_POSTGRES = True
    except Exception:
        # Se o pacote não estiver instalado, continuamos com SQLite
        USE_POSTGRES = False

# --- Mapeamento de Nomes de Tabelas e Colunas ---
# Isso permite que o código funcione com schemas diferentes (SQLite vs. Postgres)

if USE_POSTGRES:
    # Nomes para o schema PostgreSQL (singular)
    T_CATEGORIAS = "categoria"
    T_BANCOS = "banco"
    T_CARTOES = "cartao"
    T_LANCAMENTOS = "lancamento"
    # Mapeamento de colunas para a tabela de lançamento
    C_LANC_ID = "id"
    C_LANC_DATA = "data_lancamento" # Postgres usa 'date', SQLite usa dia/mes/ano
    C_LANC_DESCRICAO = "descricao"
    C_LANC_VLR_PREVISTO = "valor_previsto"
    C_LANC_VLR_PAGO = "valor_real" # Postgres usa 'valor_real'
    C_LANC_ID_CATEGORIA = "id_categoria" # Postgres usa 'id_categoria'
    C_LANC_ID_BANCO = "id_banco"
    C_LANC_ID_CARTAO = "id_cartao"
else:
    # Nomes para o schema SQLite (plural)
    T_CATEGORIAS = "categorias"
    T_BANCOS = "bancos"
    T_CARTOES = "cartoes"
    T_LANCAMENTOS = "lancamentos"
    
T_LANCAMENTOS_BACKUP = "lancamentos_backup"


class RowProxy:
    """Objeto que imita sqlite3.Row (acesso por índice e por nome).

    Usado para normalizar linhas retornadas pelo psycopg2 para que o restante
    do código (GUI, lógica) continue funcionando sem alterações.
    """
    def __init__(self, columns, values):
        self._cols = list(columns)
        self._vals = list(values)
        self._map = {c: self._vals[i] for i, c in enumerate(self._cols)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return self._map[key]

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)

    def keys(self):
        return self._cols


def _wrap_rows(cursor, rows):
    if not USE_POSTGRES:
        return rows
    if rows is None:
        return rows
    cols = [d[0] for d in cursor.description]
    wrapped = []
    for r in rows:
        # r pode ser tuple ou dict dependendo do cursor
        if isinstance(r, dict):
            vals = [r.get(c) for c in cols]
        else:
            vals = list(r)
        wrapped.append(RowProxy(cols, vals))
    return wrapped


def _wrap_row(cursor, row):
    if not USE_POSTGRES:
        return row
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    if isinstance(row, dict):
        vals = [row.get(c) for c in cols]
    else:
        vals = list(row)
    return RowProxy(cols, vals)


def conectar():
    """Retorna uma conexão e cursor compatíveis com o restante do código.

    Se `DATABASE_URL` aponta para um PostgreSQL e o pacote estiver instalado,
    conecta ao Postgres e adapta a execução de queries (substitui '?' por '%s')
    para compatibilidade com as queries existentes no projeto.
    Caso contrário, mantém o comportamento original com sqlite3.
    """
    if USE_POSTGRES:
        conn = _psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=_psycopg2.extras.RealDictCursor)

        # Ajusta o método execute para substituir placeholders '?' por '%s'
        orig_execute = cursor.execute

        def execute(query, params=None):
            q = query.replace('?', '%s')
            if params is None:
                return orig_execute(q)
            return orig_execute(q, params)

        cursor.execute = execute
        return conn, cursor

    # Fall back para SQLite
    conn = sqlite3.connect('financeiro.db', timeout=20)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome
    return conn, conn.cursor()


def criar_tabelas():
    """Cria as tabelas do banco de dados se não existirem."""
    # Se estivermos usando PostgreSQL assumimos que a estrutura
    # já foi criada pelo usuário/admin. Não tentamos aplicar DDL
    # que foi escrito para SQLite (ex: AUTOINCREMENT, sqlite_master etc.).
    if USE_POSTGRES:
        return

    conn, cursor = conectar()
    
    # Verificar se existe backup para restaurar
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?;
    """)
    tem_backup = cursor.fetchone() is not None

    # --- Tabelas de pré-cadastro ---
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS categorias
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       nome
                       TEXT
                       NOT
                       NULL
                       UNIQUE
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS bancos
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       nome
                       TEXT
                       NOT
                       NULL
                       UNIQUE
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS cartoes
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       nome
                       TEXT
                       NOT
                       NULL
                       UNIQUE
                   )
                   ''')

    # --- Tabela principal de lançamentos ---
    # Primeiro, vamos fazer backup da tabela existente se ela existir
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS lancamentos_backup AS
        SELECT * FROM {T_LANCAMENTOS};
    """)
    
    # Agora podemos dropar a tabela antiga
    cursor.execute(f"DROP TABLE IF EXISTS {T_LANCAMENTOS};")
    
    # E criar a nova tabela com a estrutura correta
    cursor.execute('''
                   CREATE TABLE lancamentos
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       dia INTEGER NOT NULL,
                       mes INTEGER NOT NULL,
                       ano INTEGER NOT NULL,
                       descricao TEXT NOT NULL,
                       valor_previsto REAL DEFAULT NULL,
                       valor_pago REAL DEFAULT NULL,
                       categoria_id INTEGER,
                       banco_id INTEGER,
                       cartao_id INTEGER,
                       FOREIGN
                       KEY
                   (
                       categoria_id
                   ) REFERENCES categorias
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       banco_id
                   ) REFERENCES bancos
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       cartao_id
                   ) REFERENCES cartoes
                   (
                       id
                   )
                       )
                   ''')

    conn.commit()
    conn.close()


# --- Funções CRUD para Cadastros (genéricas) ---

def adicionar_item_cadastro(tabela, nome):
    try:
        conn, cursor = conectar()
        cursor.execute(f"INSERT INTO {tabela} (nome) VALUES (?)", (nome, ))
        conn.commit()
    except Exception as e:
        # Normaliza erro de unicidade para o frontend
        msg = str(e).lower()
        if 'unique' in msg or 'duplicate' in msg or 'integrity' in msg:
            raise ValueError(f"O item '{nome}' já existe em '{tabela}'.")
        raise
    finally:
        conn.close()


def listar_itens_cadastro(tabela):
    conn, cursor = conectar()
    cursor.execute(f"SELECT * FROM {tabela} ORDER BY nome")
    itens = cursor.fetchall()
    itens = _wrap_rows(cursor, itens)
    conn.close()
    return itens


# --- Funções CRUD para Lançamentos ---

def restaurar_backup():
    """Restaura os dados do backup."""
    # Esta operação foi implementada originalmente para SQLite
    # (manipula arquivo DB). Para PostgreSQL não fazemos restauração
    # automática aqui — assume-se que o banco está pronto.
    if USE_POSTGRES:
        return True

    with sqlite3.connect('financeiro.db', timeout=20) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            
            # Primeiro, vamos limpar a tabela atual
            cursor.execute(f"DELETE FROM {T_LANCAMENTOS};")
            
            # Agora vamos copiar os dados do backup
            cursor.execute(f"""
                INSERT INTO {T_LANCAMENTOS} 
                SELECT id, dia, mes, ano, descricao, 
                       valor_previsto,
                       valor_pago,
                       categoria_id, banco_id, cartao_id
                FROM lancamentos_backup
            """)
            
            cursor.execute("COMMIT")
            return True
        except:
            cursor.execute("ROLLBACK")
            raise

def migrar_estrutura_lancamentos():
    """Migra a estrutura da tabela lancamentos para permitir valores nulos."""
    import os
    import shutil
    from datetime import datetime
    
    # Criar backup do banco de dados antes de qualquer alteração
    db_path = 'financeiro.db'
    backup_path = f'financeiro_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    # Fazer backup do arquivo original
    shutil.copy2(db_path, backup_path)
    
    if USE_POSTGRES:
        # Migração específica de arquivo/PRAGMA não aplicável a PostgreSQL
        return

    with sqlite3.connect(db_path, timeout=20) as conn:
        cursor = conn.cursor()
        
        # Verificar se existem dados na tabela
        cursor.execute(f"SELECT COUNT(*) FROM {T_LANCAMENTOS};")
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Se houver dados, vamos alterar a tabela mantendo os dados
            cursor.execute("PRAGMA foreign_keys=off")
            
            try:
                cursor.execute("BEGIN TRANSACTION")
                
                # Primeiro, vamos renomear a tabela atual para backup
                cursor.execute(f'ALTER TABLE {T_LANCAMENTOS} RENAME TO lancamentos_old;')
                
                # Criar nova tabela com a estrutura correta
                cursor.execute('''
                    CREATE TABLE lancamentos
                    (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dia INTEGER NOT NULL,
                        mes INTEGER NOT NULL,
                        ano INTEGER NOT NULL,
                        descricao TEXT NOT NULL,
                        valor_previsto REAL DEFAULT NULL,
                        valor_pago REAL DEFAULT NULL,
                        categoria_id INTEGER,
                        banco_id INTEGER,
                        cartao_id INTEGER,
                        FOREIGN KEY (categoria_id) REFERENCES categorias(id),
                        FOREIGN KEY (banco_id) REFERENCES bancos(id),
                        FOREIGN KEY (cartao_id) REFERENCES cartoes(id)
                    )
                ''')
                
                # Copiar dados da tabela antiga para a nova
                cursor.execute(f'''
                    INSERT INTO {T_LANCAMENTOS} 
                    SELECT id, dia, mes, ano, descricao, 
                           valor_previsto,
                           valor_pago,
                           categoria_id, banco_id, cartao_id
                    FROM lancamentos_old
                ''')
                
                # Verificar se a cópia foi bem sucedida
                cursor.execute(f"SELECT COUNT(*) FROM {T_LANCAMENTOS};")
                new_count = cursor.fetchone()[0]
                
                if new_count == count:
                    # Se a cópia foi bem sucedida, podemos remover a tabela antiga
                    cursor.execute('DROP TABLE lancamentos_old;')
                    cursor.execute("COMMIT")
                else:
                    # Se algo deu errado, fazemos rollback
                    raise Exception("Erro na migração: contagem de registros não confere")
                    
            except Exception as e:
                cursor.execute("ROLLBACK")
                # Restaurar tabela original se algo deu errado
                cursor.execute(f'DROP TABLE IF EXISTS {T_LANCAMENTOS};')
                cursor.execute(f'ALTER TABLE lancamentos_old RENAME TO {T_LANCAMENTOS};')
                raise e
            finally:
                cursor.execute("PRAGMA foreign_keys=on")

def adicionar_lancamento(dados):
    conn, cursor = conectar()
    try:
        # Garantir que os valores podem ser nulos
        valor_previsto = dados.get('valor_previsto')
        valor_pago = dados.get('valor_pago')
        
        if USE_POSTGRES:
            from datetime import date
            data_lanc = date(dados['ano'], dados['mes'], dados['dia'])
            query = f"""
                INSERT INTO {T_LANCAMENTOS} 
                    ({C_LANC_DATA}, {C_LANC_DESCRICAO}, {C_LANC_ID_CATEGORIA}, {C_LANC_ID_BANCO}, {C_LANC_ID_CARTAO}, {C_LANC_VLR_PREVISTO}, {C_LANC_VLR_PAGO})
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (data_lanc, dados['descricao'], dados['categoria_id'], dados['banco_id'], dados['cartao_id'], valor_previsto, valor_pago)
        else:
            query = f"""
                INSERT INTO {T_LANCAMENTOS} 
                    (dia, mes, ano, descricao, categoria_id, banco_id, cartao_id, valor_previsto, valor_pago)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (dados['dia'], dados['mes'], dados['ano'], dados['descricao'], dados['categoria_id'],
                      dados['banco_id'], dados['cartao_id'], valor_previsto, valor_pago)

        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        raise e
    finally:
        conn.close()


def atualizar_lancamento(id_lancamento, dados):
    conn, cursor = conectar()
    try:
        # Garantir que os valores podem ser nulos
        valor_previsto = dados.get('valor_previsto')
        valor_pago = dados.get('valor_pago')

        if USE_POSTGRES:
            from datetime import date
            data_lanc = date(dados['ano'], dados['mes'], dados['dia'])
            query = f"""
                UPDATE {T_LANCAMENTOS}
                SET {C_LANC_DATA}=?, {C_LANC_DESCRICAO}=?, {C_LANC_ID_CATEGORIA}=?, 
                    {C_LANC_ID_BANCO}=?, {C_LANC_ID_CARTAO}=?, {C_LANC_VLR_PREVISTO}=?, {C_LANC_VLR_PAGO}=?
                WHERE {C_LANC_ID} = ?
            """
            params = (data_lanc, dados['descricao'], dados['categoria_id'], dados['banco_id'], 
                      dados['cartao_id'], valor_previsto, valor_pago, id_lancamento)
        else:
            query = f"""
               UPDATE {T_LANCAMENTOS}
               SET dia=?, mes=?, ano=?, descricao=?, categoria_id=?,
                   banco_id=?, cartao_id=?, valor_previsto=?, valor_pago=?
               WHERE id = ?
            """
            params = (dados['dia'], dados['mes'], dados['ano'], dados['descricao'], dados['categoria_id'],
                      dados['banco_id'], dados['cartao_id'], valor_previsto, valor_pago, id_lancamento)

        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        raise e
    finally:
        conn.close()


def excluir_lancamento(id_lancamento):
    conn, cursor = conectar()
    if USE_POSTGRES:
        id_col = C_LANC_ID
    else:
        id_col = "id"
    cursor.execute(f"DELETE FROM {T_LANCAMENTOS} WHERE {id_col}=?;", (id_lancamento,))
    conn.commit()
    conn.close()


def listar_lancamentos_filtrados(mes=None, ano=None, somente_previsto=False):
    conn, cursor = conectar()

    if USE_POSTGRES:
        query = f"""
            SELECT l.{C_LANC_ID} as id,
                   EXTRACT(DAY FROM l.{C_LANC_DATA}) as dia,
                   EXTRACT(MONTH FROM l.{C_LANC_DATA}) as mes,
                   EXTRACT(YEAR FROM l.{C_LANC_DATA}) as ano,
                   l.{C_LANC_DESCRICAO} as descricao,
                   c.nome as categoria,
                   b.nome as banco,
                   cr.nome as cartao,
                   l.{C_LANC_VLR_PREVISTO} as valor_previsto,
                   l.{C_LANC_VLR_PAGO} as valor_pago
            FROM {T_LANCAMENTOS} l
                 LEFT JOIN {T_CATEGORIAS} c ON l.{C_LANC_ID_CATEGORIA} = c.id
                 LEFT JOIN {T_BANCOS} b ON l.{C_LANC_ID_BANCO} = b.id
                 LEFT JOIN {T_CARTOES} cr ON l.{C_LANC_ID_CARTAO} = cr.id
        """
    else: # SQLite
        query = f"""
                SELECT l.id, l.dia, l.mes, l.ano, l.descricao,
                       c.nome as categoria, b.nome as banco, cr.nome as cartao,
                       l.valor_previsto, l.valor_pago
                FROM {T_LANCAMENTOS} l
                         LEFT JOIN {T_CATEGORIAS} c ON l.categoria_id = c.id
                         LEFT JOIN {T_BANCOS} b ON l.banco_id = b.id
                         LEFT JOIN {T_CARTOES} cr ON l.cartao_id = cr.id
                """

    conditions = []
    params = []

    if mes:
        conditions.append(f"EXTRACT(MONTH FROM l.{C_LANC_DATA}) = ?" if USE_POSTGRES else "l.mes = ?")
        params.append(mes)
    if ano:
        conditions.append(f"EXTRACT(YEAR FROM l.{C_LANC_DATA}) = ?" if USE_POSTGRES else "l.ano = ?")
        params.append(ano)
    if somente_previsto:
        vlr_pago_col = C_LANC_VLR_PAGO if USE_POSTGRES else "valor_pago"
        conditions.append(f"(l.{vlr_pago_col} IS NULL OR l.{vlr_pago_col} = 0)")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if USE_POSTGRES:
        query += f" ORDER BY l.{C_LANC_DATA}"
    else:
        query += " ORDER BY l.ano, l.mes, l.dia"

    cursor.execute(query, tuple(params))
    lancamentos = cursor.fetchall()
    lancamentos = _wrap_rows(cursor, lancamentos)
    conn.close()
    return lancamentos


# --- Funções de Análise ---

def obter_soma_por_categoria(mes, ano):
    """Retorna a soma dos valores pagos agrupados por categoria para um dado mês e ano."""
    conn, cursor = conectar()
    if USE_POSTGRES:
        query = f"""
            SELECT c.nome, SUM(l.{C_LANC_VLR_PAGO}) as total
            FROM {T_LANCAMENTOS} l
            JOIN {T_CATEGORIAS} c ON l.{C_LANC_ID_CATEGORIA} = c.id
            WHERE EXTRACT(MONTH FROM l.{C_LANC_DATA}) = ? AND EXTRACT(YEAR FROM l.{C_LANC_DATA}) = ? 
              AND l.{C_LANC_VLR_PAGO} IS NOT NULL AND l.{C_LANC_VLR_PAGO} != 0
            GROUP BY c.nome
            ORDER BY total DESC
        """
    else:
        query = f"""
            SELECT c.nome, SUM(CAST(l.valor_pago AS REAL)) as total
            FROM {T_LANCAMENTOS} l
            JOIN {T_CATEGORIAS} c ON l.categoria_id = c.id
            WHERE l.mes = ? AND l.ano = ? AND l.valor_pago IS NOT NULL AND l.valor_pago != 0
            GROUP BY c.nome
            ORDER BY total DESC
        """
    cursor.execute(query, (mes, ano))
    resultado = cursor.fetchall()
    resultado = _wrap_rows(cursor, resultado)
    conn.close()
    return resultado


def obter_soma_por_banco(mes, ano):
    """Retorna a soma dos valores pagos agrupados por banco para um dado mês e ano."""
    conn, cursor = conectar()
    if USE_POSTGRES:
        query = f"""
            SELECT b.nome, SUM(l.{C_LANC_VLR_PAGO}) as total
            FROM {T_LANCAMENTOS} l
            JOIN {T_BANCOS} b ON l.{C_LANC_ID_BANCO} = b.id
            WHERE EXTRACT(MONTH FROM l.{C_LANC_DATA}) = ? AND EXTRACT(YEAR FROM l.{C_LANC_DATA}) = ? 
              AND l.{C_LANC_VLR_PAGO} IS NOT NULL AND l.{C_LANC_VLR_PAGO} != 0
            GROUP BY b.nome
            ORDER BY total DESC
        """
    else:
        query = f"""
            SELECT b.nome, SUM(CAST(l.valor_pago AS REAL)) as total
            FROM {T_LANCAMENTOS} l
            JOIN {T_BANCOS} b ON l.banco_id = b.id
            WHERE l.mes = ? AND l.ano = ? AND l.valor_pago IS NOT NULL AND l.valor_pago != 0
            GROUP BY b.nome
            ORDER BY total DESC
        """
    cursor.execute(query, (mes, ano))
    resultado = cursor.fetchall()
    resultado = _wrap_rows(cursor, resultado)
    conn.close()
    return resultado


def obter_entradas_saidas_saldo(mes, ano):
    """Calcula o total de entradas, saídas e o saldo para um dado mês e ano."""
    conn, cursor = conectar()
    if USE_POSTGRES:
        query = f"""
            SELECT
                SUM(CASE WHEN {C_LANC_VLR_PAGO} > 0 THEN {C_LANC_VLR_PAGO} ELSE 0 END) as entradas,
                SUM(CASE WHEN {C_LANC_VLR_PAGO} < 0 THEN {C_LANC_VLR_PAGO} ELSE 0 END) as saidas
            FROM {T_LANCAMENTOS}
            WHERE EXTRACT(MONTH FROM {C_LANC_DATA}) = ? AND EXTRACT(YEAR FROM {C_LANC_DATA}) = ? 
              AND {C_LANC_VLR_PAGO} IS NOT NULL AND {C_LANC_VLR_PAGO} != 0
        """
    else:
        query = f"""
            SELECT
                SUM(CASE WHEN CAST(valor_pago AS REAL) > 0 THEN CAST(valor_pago AS REAL) ELSE 0 END) as entradas,
                SUM(CASE WHEN CAST(valor_pago AS REAL) < 0 THEN CAST(valor_pago AS REAL) ELSE 0 END) as saidas
            FROM {T_LANCAMENTOS}
            WHERE mes = ? AND ano = ? AND valor_pago IS NOT NULL AND valor_pago != 0
        """
    cursor.execute(query, (mes, ano))
    resultado = cursor.fetchone()
    resultado = _wrap_row(cursor, resultado)
    conn.close()

    entradas = resultado['entradas'] or 0.0
    saidas = resultado['saidas'] or 0.0
    saldo = entradas + saidas # Saídas já são negativas
    return {'entradas': entradas, 'saidas': saidas, 'saldo': saldo}


# Garante que as tabelas sejam criadas na inicialização
criar_tabelas()