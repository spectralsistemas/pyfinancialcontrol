# Guia de Configuração do PostgreSQL

Este documento descreve como configurar um banco de dados PostgreSQL para ser usado com a aplicação "Controle Financeiro".

## 1. Instalação do PostgreSQL

Se você ainda não tem o PostgreSQL instalado, a maneira mais fácil de começar é usando o Docker.

Execute o seguinte comando para iniciar um container PostgreSQL:

```bash
docker run --name controle-financeiro-db -e POSTGRES_PASSWORD=sua_senha_aqui -p 5432:5432 -d postgres:15
```

> Substitua `sua_senha_aqui` por uma senha segura de sua escolha.

Se preferir uma instalação nativa, siga as instruções no site oficial do PostgreSQL.

## 2. Criação do Banco de Dados e Usuário

Conecte-se ao seu servidor PostgreSQL (usando `psql`, DBeaver, ou sua ferramenta preferida) e execute os seguintes comandos para criar um usuário e um banco de dados dedicados para a aplicação.

```sql
-- Crie um usuário dedicado (substitua 'minha_senha' por uma senha segura)
CREATE USER financeiro_user WITH PASSWORD 'minha_senha';

-- Crie o banco de dados
CREATE DATABASE financeiro_db;

-- Dê ao novo usuário a propriedade do banco de dados
ALTER DATABASE financeiro_db OWNER TO financeiro_user;
```

## 3. Criação da Estrutura de Tabelas (Schema)

Agora, conecte-se ao banco de dados recém-criado (`financeiro_db`) com o usuário `financeiro_user` e execute o script `scripts/schema_postgres.sql` para criar todas as tabelas necessárias.

Você pode fazer isso através da linha de comando com `psql`:

```bash
psql -h localhost -U financeiro_user -d financeiro_db -f scripts/schema_postgres.sql
```

## 4. Configuração da Aplicação

Finalmente, configure a aplicação para se conectar ao novo banco de dados. Copie o arquivo `config.ini.example` para `config.ini` e preencha com as credenciais que você acabou de criar.

Seu `config.ini` deve ficar assim:

```ini
[database]
driver = postgresql
user = financeiro_user
password = minha_senha
host = localhost
port = 5432
dbname = financeiro_db
```

Pronto! Agora você pode iniciar a aplicação, e ela se conectará ao seu banco de dados PostgreSQL.