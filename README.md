# Portal do Jornal Escolar

Portal web simples para organizar fichas de participantes, submissão de jornais e compartilhamento de arquivos do jornal escolar.

## Configuração

1. Instale as dependências (se o erro `No module named 'flask'` aparecer, rode o comando abaixo para instalar tudo de uma vez):

```bash
./install.sh
```

2. Ajuste o arquivo `config.json` na raiz para definir:
   - `protocol`: `http` ou `https` (usado para montar os links de aprovação)
   - `host`: host exposto (por exemplo, `localhost`)
   - `port`: porta onde o Flask deve iniciar
   - `admin_users`: lista de usuários e senhas de administradores

3. Execute a aplicação:

```bash
python app.py
```

A aplicação inicia na porta definida em `config.json` e salva uploads nas pastas `uploads/journals` e `uploads/assets`.

## Funcionalidades

- **Login de administrador:** somente usuários da lista `admin_users` conseguem acessar o painel.
- **Ficha de participantes:** cadastro, impressão rápida e bloqueio/liberação do acesso ao portal.
- **Jornais:** criação de edições, upload de PDF e geração de link público para aprovação/reprovação com justificativa.
- **Arquivos:** upload e download de materiais usados na produção.
- **Versões:** linha do tempo das edições cadastradas com status e motivos de reprovação quando houver.
