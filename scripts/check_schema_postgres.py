"""Script para verificar compatibilidade do schema PostgreSQL com a aplicação.

Ele tenta conectar usando `DATABASE_URL` (env) ou lendo `config.ini` na raiz.
Gera um relatório indicando tabelas/colunas faltantes, diferenças de nullability,
chaves primárias e estrangeiras faltantes e possíveis incompatibilidades de tipo.

Rode:

  python scripts/check_schema_postgres.py

Dependências: psycopg2-binary

"""
import os
import sys
import configparser
import urllib.parse

try:
    import psycopg2
    import psycopg2.extras
except Exception as e:
    print("Erro: psycopg2 não encontrado. Instale com: pip install psycopg2-binary")
    sys.exit(2)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Reusar a mesma lógica de descoberta da app
DATABASE_URL = os.environ.get('DATABASE_URL')
config_path = os.path.join(ROOT_DIR, 'config.ini')
if not DATABASE_URL and os.path.exists(config_path):
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    if 'database' in cfg:
        dbcfg = cfg['database']
        if dbcfg.get('url'):
            DATABASE_URL = dbcfg.get('url')
        else:
            driver = dbcfg.get('driver', '').lower()
            if driver in ('postgres', 'postgresql') or dbcfg.get('host'):
                user = dbcfg.get('user', '')
                pwd = dbcfg.get('password', '')
                host = dbcfg.get('host', 'localhost')
                port = dbcfg.get('port', '5432')
                dbname = dbcfg.get('dbname') or dbcfg.get('database') or ''
                if pwd:
                    pwd = urllib.parse.quote_plus(pwd)
                DATABASE_URL = f"postgresql://{user}:{pwd}@{host}:{port}/{dbname}"

if not DATABASE_URL:
    print("Nenhuma configuração de Postgres encontrada (DATABASE_URL ou config.ini). Saindo.")
    sys.exit(3)

print(f"Usando DATABASE_URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Definir o schema esperado com propriedades mínimas
# Tipo são categorias relaxadas ('int','float','text') para comparação simples
EXPECTED = {
    'categoria': {
        'columns': {
            'id': {'type': 'int', 'nullable': False, 'pk': True},
            'nome': {'type': 'text', 'nullable': False, 'unique': True},
        }
    },
    'banco': {
        'columns': {
            'id': {'type': 'int', 'nullable': False, 'pk': True},
            'nome': {'type': 'text', 'nullable': False, 'unique': True},
        }
    },
    'cartao': {
        'columns': {
            'id': {'type': 'int', 'nullable': False, 'pk': True},
            'nome': {'type': 'text', 'nullable': False, 'unique': True},
        }
    },
    'lancamento': {
        'columns': {
            'id': {'type': 'int', 'nullable': False, 'pk': True},
            'data_lancamento': {'type': 'date', 'nullable': False},
            'descricao': {'type': 'text', 'nullable': False},
            'valor_previsto': {'type': 'numeric', 'nullable': True},
            'valor_real': {'type': 'numeric', 'nullable': True},
            'id_categoria': {'type': 'int', 'nullable': False, 'fk': ('categoria', 'id')},
            'id_banco': {'type': 'int', 'nullable': True, 'fk': ('banco', 'id')},
            'id_cartao': {'type': 'int', 'nullable': True, 'fk': ('cartao', 'id')},
        }
    }
}


def get_tables():
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    return {r[0] for r in cur.fetchall()}


def get_columns(table):
    cur.execute("""
        SELECT column_name, data_type, is_nullable, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    cols = {}
    for name, data_type, is_nullable, udt_name in cur.fetchall():
        cols[name] = {'data_type': data_type, 'is_nullable': (is_nullable == 'YES'), 'udt_name': udt_name}
    return cols


def get_primary_keys(table):
    cur.execute("""
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_name = %s
      AND tc.table_schema = 'public'
    ORDER BY kcu.ordinal_position
    """, (table,))
    return [r[0] for r in cur.fetchall()]


def get_uniques(table):
    cur.execute("""
    SELECT kcu.column_name, tc.constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'UNIQUE'
      AND tc.table_name = %s
      AND tc.table_schema = 'public'
    """, (table,))
    res = cur.fetchall()
    uniques = {r[0] for r in res}
    return uniques


def get_foreign_keys(table):
    cur.execute("""
    SELECT
      kcu.column_name,
      ccu.table_name AS foreign_table_name,
      ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
     AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s AND tc.table_schema = 'public';
    """, (table,))
    fks = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    return fks


def normalize_type(udt_name, data_type):
    # Simplified normalization
    if data_type in ('integer',) or udt_name in ('int4', 'int2', 'int8'):
        return 'int'
    if data_type in ('real', 'double precision',) or udt_name in ('float4', 'float8'):
        return 'float'
    if data_type in ('numeric', 'decimal'):
        return 'numeric'
    if data_type in ('character varying', 'text', 'character'):
        return 'text'
    if data_type == 'date':
        return 'date'
    return data_type


def check_table(table, spec):
    issues = []
    cols = get_columns(table)
    pks = get_primary_keys(table)
    uniques = get_uniques(table)
    fks = get_foreign_keys(table)

    expected_cols = spec.get('columns', {})
    # Missing columns
    for col, props in expected_cols.items():
        if col not in cols:
            issues.append(f"MISSING COLUMN: {col}")
            continue
        actual = cols[col]
        ntype = normalize_type(actual['udt_name'], actual['data_type'])
        exp_type = props.get('type')
        if exp_type and exp_type != ntype:
            # Tipos relaxados: int vs numeric/float are warnings
            if not (exp_type in ('float', 'numeric') and ntype in ('numeric','float','double precision')):
                issues.append(f"TYPE MISMATCH for {col}: expected {exp_type}, actual {ntype}")
        # Nullability
        if props.get('nullable') is False and actual['is_nullable']:
            issues.append(f"NULLABILITY MISMATCH for {col}: expected NOT NULL")
        if props.get('nullable') is True and not actual['is_nullable']:
            issues.append(f"NULLABILITY MISMATCH for {col}: expected NULLABLE")
        # PK
        if props.get('pk') and col not in pks:
            issues.append(f"PRIMARY KEY MISSING on column {col}")
        # Unique
        if props.get('unique') and col not in uniques:
            issues.append(f"UNIQUE constraint missing on {col}")
        # FK
        if 'fk' in props:
            fk = props['fk']
            actual_fk = fks.get(col)
            if not actual_fk:
                issues.append(f"FOREIGN KEY missing on {col} expected -> {fk[0]}({fk[1]})")
            else:
                if actual_fk[0] != fk[0] or actual_fk[1] != fk[1]:
                    issues.append(f"FOREIGN KEY mismatch on {col}: expected {fk}, actual {actual_fk}")

    # Extra columns (not fatal, just informative)
    extra = set(cols.keys()) - set(expected_cols.keys())
    if extra:
        issues.append(f"EXTRA COLUMNS: {', '.join(sorted(extra))}")

    return issues


def main():
    tables = get_tables()
    ok = True
    for table, spec in EXPECTED.items():
        print('\nChecking table:', table)
        if table not in tables:
            print('  => MISSING TABLE')
            ok = False
            continue
        issues = check_table(table, spec)
        if not issues:
            print('  => OK')
        else:
            ok = False
            for it in issues:
                print('  -', it)

    if ok:
        print('\nSchema parece compatível (verificações básicas).')
        sys.exit(0)
    else:
        print('\nForam encontradas incompatibilidades. Revise os itens acima.')
        sys.exit(4)


if __name__ == '__main__':
    try:
        main()
    finally:
        cur.close()
        conn.close()
