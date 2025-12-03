# Portal do Jornal Escolar

Portal web simples para organizar fichas de participantes, submissão de jornais e compartilhamento de arquivos do jornal escolar.

## Configuração

1. Instale as dependências (se o erro `No module named 'flask'` aparecer, rode o comando abaixo para instalar tudo de uma vez). O pacote `cryptography` já é instalado automaticamente e é usado para gerar um certificado temporário quando você pedir HTTPS sem fornecer arquivos reais:

```bash
./install.sh
```

2. Ajuste o arquivo `config.json` na raiz para definir:
   - `protocol`: `http` ou `https` (usado para montar os links de aprovação)
   - `host`: host exposto (por exemplo, `localhost`)
   - `port`: porta onde o Flask deve iniciar
   - `admin_users`: lista de usuários e senhas de administradores
   - `ssl_certificate` e `ssl_key`: caminhos para o certificado e a chave privada caso você já tenha um par válido

3. Execute a aplicação:

```bash
python app.py
```

A aplicação inicia na porta definida em `config.json` e salva uploads nas pastas `uploads/journals` e `uploads/assets`.

## Adicionando seu certificado SSL

1. Coloque seus arquivos de certificado (normalmente `.crt` ou `.pem`) e sua chave privada (`.key`) em uma pasta local (por exemplo `certs/`). Os arquivos reais são ignorados pelo git.
2. Atualize o `config.json` para apontar para esses caminhos quando `protocol` estiver como `https`:

```json
{
  "protocol": "https",
  "ssl_certificate": "certs/seu_certificado.pem",
  "ssl_key": "certs/sua_chave.key",
  ...
}
```

3. Inicie a aplicação normalmente (`python app.py`). Se os caminhos existirem, o Flask usará seu certificado; se estiverem vazios ou inválidos e o pacote `cryptography` estiver instalado, ele gera um certificado temporário apenas para testes. Caso contrário, o servidor volta para HTTP automaticamente e exibirá um aviso.

## Funcionalidades

- **Login de administrador:** somente usuários da lista `admin_users` conseguem acessar o painel.
- **Ficha de participantes:** cadastro, impressão rápida e bloqueio/liberação do acesso ao portal.
- **Jornais:** criação de edições, upload de PDF e geração de link público para aprovação/reprovação com justificativa.
- **Arquivos:** upload e download de materiais usados na produção.
- **Versões:** linha do tempo das edições cadastradas com status e motivos de reprovação quando houver.
