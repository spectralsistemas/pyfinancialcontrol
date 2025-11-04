-- Script para criação do schema do banco de dados no PostgreSQL
-- para a aplicação Controle Financeiro.

-- Tabela de Categorias
CREATE TABLE categoria (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

-- Tabela de Bancos
CREATE TABLE banco (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

-- Tabela de Cartões
CREATE TABLE cartao (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

-- Tabela principal de Lançamentos
CREATE TABLE lancamento (
    id SERIAL PRIMARY KEY,
    data_lancamento DATE NOT NULL,
    descricao TEXT NOT NULL,
    valor_previsto NUMERIC(10, 2),
    valor_real NUMERIC(10, 2),
    id_categoria INTEGER NOT NULL,
    id_banco INTEGER,
    id_cartao INTEGER,

    CONSTRAINT fk_categoria
        FOREIGN KEY(id_categoria) 
        REFERENCES categoria(id),

    CONSTRAINT fk_banco
        FOREIGN KEY(id_banco) 
        REFERENCES banco(id),

    CONSTRAINT fk_cartao
        FOREIGN KEY(id_cartao) 
        REFERENCES cartao(id)
);

-- Índices para otimizar consultas de filtro e junções
CREATE INDEX idx_lancamento_data ON lancamento(data_lancamento);
CREATE INDEX idx_lancamento_categoria ON lancamento(id_categoria);
CREATE INDEX idx_lancamento_banco ON lancamento(id_banco);
CREATE INDEX idx_lancamento_cartao ON lancamento(id_cartao);