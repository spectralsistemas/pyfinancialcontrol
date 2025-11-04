# Controle Financeiro

Um aplicativo de desktop para gerenciamento financeiro pessoal desenvolvido em Python, utilizando Tkinter para a interface gráfica e SQLite para armazenamento de dados.

## Funcionalidades

- Interface gráfica amigável
- Cadastro e gerenciamento de categorias
- Cadastro e gerenciamento de bancos e cartões
- Armazenamento local dos dados em banco SQLite
- Interface adaptada para sistemas Windows e macOS

## Requisitos

- Python 3.x
- pyobjc (apenas para macOS)
- pyinstaller (opcional, para criar executáveis)

## Instalação

1. Clone ou faça download deste repositório
2. Crie um ambiente virtual (recomendado):
   ```bash
   python -m venv .venv
   ```
3. Ative o ambiente virtual:
   - No macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - No Windows:
     ```bash
     .venv\Scripts\activate
     ```
4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Como Executar

1. Navegue até a pasta do projeto:
   ```bash
   cd caminho/para/financial
   ```

2. Execute o programa:
   ```bash
   python -m app.main
   ```

## Gerar Executável (Opcional)

Para transformar o programa em um executável, execute o seguinte comando na raiz do projeto. Ele utiliza o `pyinstaller`, que já deve estar instalado a partir do `requirements.txt`.

```bash
pyinstaller --name "Controle Financeiro" --windowed --onefile --icon="config/icone.icns" --add-data "config.ini:." --paths "./app" run.py
```

## Estrutura do Projeto

```
financial/
├── app/
│   ├── __init__.py
│   ├── database.py    # Gerenciamento do banco de dados SQLite
│   ├── gui.py         # Interface gráfica usando Tkinter
│   └── main.py        # Ponto de entrada do programa
├── requirements.txt    # Dependências do projeto
└── README.md          # Este arquivo
```

## Base de Dados

O programa utiliza um banco de dados SQLite (`financeiro.db`) que será criado automaticamente na primeira execução do programa. Todos os dados são armazenados localmente no seu computador.

## Configuração de conexão via arquivo (opcional)

Além de poder configurar a conexão via variável de ambiente `DATABASE_URL`, você também pode criar um arquivo `config.ini` na raiz do projeto com a seção `[database]` para informar as credenciais.

Coloque um arquivo `config.ini` (ou copie `config.ini.example`) com um dos formatos abaixo:

- URL completa (Postgres):

   [database]
   url = postgresql://usuario:senha@host:5432/nome_do_banco

- Campos separados (Postgres):

   [database]
   driver = postgresql
   user = usuario
   password = senha
   host = 127.0.0.1
   port = 5432
   dbname = nome_do_banco

- Arquivo SQLite local:

   [database]
   driver = sqlite
   file = financeiro.db

O comportamento é: a aplicação prefere `DATABASE_URL` (variável de ambiente). Se não existir, ela procura por `config.ini`. Se nada for encontrado, continuará usando um arquivo `financeiro.db` local (SQLite).

## Contribuição

Sinta-se à vontade para contribuir com o projeto através de issues ou pull requests.