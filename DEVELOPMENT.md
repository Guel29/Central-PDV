# Testar sem instalador — Central e Agent Windows

## Laboratório em duas abas

Com Python 3.12 instalado, abra PowerShell na pasta do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -TrustLocalCertificate
```

O script prepara `.venv`, um certificado local e dados separados em `%LOCALAPPDATA%\SmartPDV\development`. A opção explícita `-TrustLocalCertificate` confere o SHA-256 antes de adicionar o certificado à confiança do usuário Windows; não desliga TLS. Python Microsoft Store é suportado pela resolução do caminho físico. Não há usuário, senha ou tela de login: a Central abre direto no dashboard.

Clique **Abrir Agent simulado** para abrir a segunda aba. Este laboratório orquestra Central e dois Agents como tarefas independentes, conectadas pelo protocolo TCP/IP/WebSocket TLS real, mas **desktop, captura, F11 e entrada Windows são simulados**. A tela diz “DESKTOP SIMULADO”; não é uma captura do seu computador. Não é necessário manter essa aba aberta no uso real do caixa.

Ative o som na Central. No painel Agent, solicite liberação no PDV 1 e PDV 2, teste os cards verdes e repetição de três bipes a cada dez segundos. Clique no card; digite e use Enter ou clique em LIBERAR TESTE para liberar a venda sintética. Teste alternância, tela cheia, encerrar, desconectar/reconectar e limpar venda simulada. O botão de chamado sempre funciona; F11 na aba pode ser reservado pelo navegador e não é o hotkey global Windows.

HTML/CSS/JS se recarregam em aproximadamente 1,5 segundo após edição. O atendimento em curso é encerrado na recarga. Para mudanças Python, pare com Ctrl+C e execute novamente. O dashboard volta sem login. Dados e certificado do laboratório persistem; não aponte `--data` para dados de produção.

Este ambiente do Codex não oferece uma ferramenta de prévia lateral/porta pública. Loopback da máquina do Codex não é acessível pelo seu navegador; capturas nesta conversa não são uma interface interativa. Execute localmente para clicar em tempo real.

## Agent real — dois computadores Windows na mesma LAN

Em ambos, na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No administrador:

```powershell
.\.venv\Scripts\python.exe -m smartpdv central setup
.\.venv\Scripts\python.exe -m smartpdv central add-pdv
.\.venv\Scripts\python.exe -m smartpdv central trust-certificate
.\.venv\Scripts\python.exe -m smartpdv central
```

Informe o IP/nome LAN na configuração; cada cadastro de PDV recebe um número único, UUID e credencial. Reinicie após novos cadastros. Transfira o pareamento por mídia segura ao caixa.

No computador do caixa:

```powershell
.\.venv\Scripts\python.exe -m smartpdv agent setup
.\.venv\Scripts\python.exe -m smartpdv agent
```

Selecione o pareamento e confirme o endereço e o número do caixa. Exclua cópias do arquivo após importar. Esse comando usa captura, F11 global, mouse, teclado e rolagem **reais**, na sessão Windows do operador. No computador Central, abra o navegador no endereço HTTPS configurado, porta 8443, confie no certificado verificado e permita essa porta somente na sub-rede privada, conforme README.md. O dashboard é restrito ao próprio computador Central, sem login do aplicativo. O Agent do caixa continua autenticado por credencial individual e pin TLS.

A versão por código-fonte mantém o terminal enquanto roda. Para iniciar sem terminal e automaticamente ao entrar no usuário Windows, configure primeiro o Agent, feche a instância manual (Ctrl+C) e execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\agent-startup.ps1 -StartNow
```

Esse script valida o cadastro/DPAPI, cria um atalho identificado na pasta Inicializar do usuário atual e usa `pythonw.exe`. Não inicia antes do login nem oculta o processo do Gerenciador de Tarefas. Mantenha projeto e `.venv` no mesmo lugar. Para remover só o início automático:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\agent-startup.ps1 -Remove
```

O usuário Windows que configura o Agent deve ser o mesmo que o executa (DPAPI). Use o instalador Agent se não quiser instalar Python no caixa; o pacote inclui o runtime e configura inicialização no login.

## Validar e atualizar

```sh
python -m pip install -r requirements-browser.txt
python -m pytest -q
python tests/development_browser.py
python tests/browser_smoke.py
```

Chromium deve estar disponível em `/usr/bin/chromium` ou em `CHROMIUM_PATH`. Testes usam certificados e credenciais de PDV temporários, verificam TLS e não precisam de contas de usuário do app. O teste nativo de ACL/DPAPI só executa no Windows. Captura física, interação com o software de vendas, UAC e desempenho devem ser testados nos computadores de destino.

Para atualizar, com os aplicativos parados use `git pull --ff-only` sem alterações locais, ou extraia um novo ZIP em pasta separada e preserve suas edições e dados. Senhas/cadastros de supervisores antigos são ignorados; não há login para a Central. Não apague certificados ou pareamentos existentes. Para consultar o caminho físico dos dados de laboratório: `python -m smartpdv.dev --print-data-directory`.

Para parar a Central por código-fonte, use Ctrl+C. Nos executáveis sem console, fechar a aba do navegador não encerra o servidor; finalize apenas o processo SmartPDV-Central.exe que você iniciou quando precisar alterar a configuração/reiniciar. O Agent permanece em segundo plano, reconectando sozinho quando a Central volta.
