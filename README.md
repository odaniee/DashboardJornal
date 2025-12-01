# Portal do Jornal Escolar

Portal web em Flask para organizar fichas de participantes, submissão de jornais, comunicação interna e compartilhamento de arquivos do jornal escolar.

## Configuração

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Ajuste o arquivo `config.json` na raiz para definir:
   - `protocol`: `http` ou `https` (usado para montar os links públicos)
   - `host`: host exposto (por exemplo, `localhost`)
   - `port`: porta onde o Flask deve iniciar (padrão **8445**)
   - `ssl_certificate` e `ssl_key`: caminhos absolutos para os arquivos `.crt/.pem` e `.key` quando usar HTTPS
   - `admin_users`: lista de usuários e senhas de administradores
   - `debug` (opcional): deixe como `false` em produção para evitar logs sensíveis

3. Execute a aplicação:

```bash
python app.py
```

A aplicação inicia na porta definida em `config.json` (por padrão 8445) e salva uploads nas pastas `uploads/journals` e `uploads/assets`. Se `protocol` estiver como `https` e os arquivos informados em `ssl_certificate` e `ssl_key` existirem, o servidor Flask sobe já com TLS habilitado.

## Estrutura de dados
- `data/students.json`: fichas dos participantes
- `data/journals.json`: submissões de jornais
- `data/assets.json`: acervo pessoal e por departamento
- `data/rules.json`: manual de regras editável
- `data/announcements.json`: canal de recados administrativos
- `data/calendar.json`: eventos gerais e por departamento
- `data/departments.json`: departamentos, filas e membros
- `data/tickets.json`: tickets de suporte e conversas com a diretoria
- `data/site_settings.json`: ajustes de identidade visual

## Funcionalidades
- **Login de administrador:** apenas usuários definidos em `config.json` acessam o painel.
- **Manual de regras:** documento editável pelos administradores.
- **Canal administrativo:** mensagens e recados fixáveis para a equipe.
- **Calendário:** eventos gerais e por departamento com datas e descrições.
- **Ficha de participantes:** cadastro, impressão rápida e bloqueio/liberação do acesso ao portal.
- **Departamentos:** criação, fila pública de entrada por link dedicado, aprovação de diretor e quadro de membros.
- **Jornais:** criação de edições, upload de PDF e geração de link público para aprovação/reprovação com justificativa.
- **Arquivos:** upload e download de materiais pessoais ou por departamento (estilo drive interno).
- **Versões:** linha do tempo das edições cadastradas com status e motivos de reprovação quando houver.
- **Tickets de ajuda:** abertura de chamados com motivo, título e urgência, com chat interno; diretores podem responder, fechar ou apagar tickets.
- **Identidade visual:** escolha de logo, cor principal e cor de destaque diretamente no painel.
- **Widgets customizáveis:** cards de métricas e recados no topo do dashboard, ativados/renomeados pela guia de configurações.

## Segurança e limitações
- Uploads são limitados a 16MB e extensões conhecidas (PDF para jornais; PDF, imagens e documentos comuns para arquivos).
- A flag `debug` é desativada por padrão; configure usuários administradores com senhas fortes no `config.json`.
