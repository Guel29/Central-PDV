# Smart PDV Control

Central e Agent para Windows 10/11 x64, criados do zero. Execução exclusivamente na LAN, sem banco de dados, CDN, telemetria, API externa ou serviços de nuvem. Python 3.12 é necessário **somente para desenvolvimento/build**; os instaladores incluem o runtime.

## Arquitetura implementada

- A Central hospeda o dashboard HTTPS e o endpoint WebSocket TLS na porta 8443. O Agent abre a conexão; nenhuma porta de entrada é necessária nos caixas.
- Cada cadastro tem número do PDV, UUID e credencial aleatória exclusiva. O Agent valida o SHA-256 do certificado da Central antes de enviar credenciais. A Central rejeita conexões com credenciais incorretas, duplicadas e de endereços públicos. O Agent resolve nomes locais e rejeita destinos públicos.
- Supervisores autenticam com senha PBKDF2-SHA256 (600.000 iterações), cookie Secure/HttpOnly/SameSite, expiração em oito horas, limite de tentativas e verificação de Origin. Permissão de visualização ou de controle; apenas um atendimento por PDV, vinculado à conexão do supervisor.
- Estado do dashboard e capturas ficam apenas em memória. Miniaturas JPEG de até 320×180 a cada dois segundos; atendimento de até 1280×720, quatro quadros por segundo. Fluxo por WebSocket, sem gravação de telas.
- F11 global solicita liberação. O card pisca verde; o alarme produz três bipes e repete a cada dez segundos enquanto houver pedidos online. Clique inicia atendimento, retira a pendência e permite mouse/teclado. Encerramento devolve o card ao amarelo. Offline é cinza. Atendimento ativo é azul.
- Reconexão automática com espera progressiva de 1–15 segundos. Pedidos ainda pendentes no Agent são reenviados após reinício da Central. Encerramento/desconexão libera teclas e botões pressionados. Estado transitório não persiste após fechar o Agent.

## Desenvolvimento e validação

```sh
python3 -m venv /workspace/smartpdv-venv
/workspace/smartpdv-venv/bin/python -m pip install -r requirements-dev.txt
/workspace/smartpdv-venv/bin/python -m pytest -q
node --check smartpdv/web/app.js
```

`requirements-lock.txt` fixa também as dependências transitivas, com dependências específicas de Windows condicionais. Testes usam certificados, credenciais e diretórios temporários próprios; não exigem segredos de produção. Exercitam TLS real em loopback, autenticação, permissões, encaminhamento de comandos, logs, escrita atômica e reconexão após reinício. O desktop é substituído por um adaptador de teste no Linux; isso não valida APIs Windows.

Teste opcional do navegador: instalar `requirements-browser.txt`, disponibilizar Chromium e executar `python tests/browser_smoke.py`. O teste confia apenas na chave pública do certificado temporário por pin SPKI; não desliga a verificação TLS globalmente. Define `CHROMIUM_PATH` se o executável não estiver em `/usr/bin/chromium`.

## Gerar os dois instaladores

Em Windows x64, instalar Python 3.12 e Inno Setup 6 no computador de build. Na raiz:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Também há um workflow manual **Windows installers** em `.github/workflows/windows-build.yml`, que gera e disponibiliza os dois instaladores como artefato após publicar este código no GitHub. O workflow não foi executado aqui.

Saídas esperadas:

- `dist/installers/SmartPDV-Central-Setup.exe`
- `dist/installers/SmartPDV-Agent-Setup.exe`

O script verifica falhas de cada comando e usa PyInstaller onedir com dependências e arquivos web inclusos. Inno Setup instala os arquivos por usuário e oferece inicialização ao entrar no Windows. Os instaladores não baixam pacotes durante a instalação. Executáveis Windows precisam ser gerados no Windows; não foram gerados nem executados neste ambiente Linux. Não há assinatura Authenticode configurada.

## Instalar e parear na LAN

1. Instale a Central no computador supervisor. Abra **Configuração inicial** no menu Iniciar. Informe o IP/nome LAN, supervisor e senha de pelo menos 12 caracteres. Use IP reservado no DHCP ou nome local estável.
2. Abra **Cadastrar PDV** para cada caixa. O cadastro cria um arquivo de pareamento em `%LOCALAPPDATA%\SmartPDV\central\pairing\pdv-N.json`. Ele contém uma credencial de bootstrap: transfira diretamente por mídia segura, importe no Agent e exclua as cópias depois. Não envie esse arquivo para Git ou logs. Não reaproveite o cadastro em outro caixa.
3. Instale o Agent. Em **Configuração inicial**, selecione o caminho do pareamento e confirme o endereço da Central e o número do PDV. A credencial importada é protegida com DPAPI para o usuário Windows atual. Configure e execute sob o mesmo usuário do operador; os perfis Windows diferentes precisam de configuração própria.
4. Inicie a Central e os Agents pelos atalhos. Cada Agent roda na sessão interativa do operador, necessária para F11, captura e entrada remota. Nenhum servidor dedicado é exigido.
5. Configure a rede Windows como Privada. Permita TCP 8443 **somente na Central, no perfil privado e para a sub-rede local**. Se necessário, um administrador pode executar:

   ```powershell
   New-NetFirewallRule -DisplayName 'SmartPDV LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -RemoteAddress LocalSubnet -Profile Private
   ```

6. No navegador da Central, use o endereço HTTPS do IP/nome configurado, porta 8443. O certificado é local, gerado na configuração. Antes de confiar nele, compare seu SHA-256 com `fingerprint` no `central.json` por um canal local seguro (`certutil -hashfile central.crt SHA256` calcula o hash do arquivo PEM, **não** o fingerprint DER; não confunda os dois). Para obter o fingerprint do certificado em desenvolvimento: `openssl x509 -in central.crt -noout -fingerprint -sha256`. Importe o certificado verificado no armazenamento de confiança do usuário Windows; não desative a verificação TLS. O Agent já faz validação por fingerprint e dispensa essa importação.
7. Entre no dashboard e clique **Ativar alarme sonoro** uma vez. Navegadores exigem interação antes de emitir áudio. Mantenha o dashboard aberto e o volume habilitado.

Para desenvolvimento, os mesmos fluxos estão disponíveis por CLI:

```sh
python -m smartpdv central setup --data CAMINHO_CENTRAL
python -m smartpdv central add-pdv --data CAMINHO_CENTRAL
python -m smartpdv central add-supervisor --data CAMINHO_CENTRAL
python -m smartpdv central --data CAMINHO_CENTRAL
python -m smartpdv agent setup --data CAMINHO_AGENT
python -m smartpdv agent --data CAMINHO_AGENT
```

Não há senha inicial ou conta padrão embutida. Não é necessário token GitHub, Firebase, Supabase, serviço externo ou conexão com internet para operar.

## Configurações, permissões e histórico

Dados ficam em `%LOCALAPPDATA%\SmartPDV\central` e `...\agent` (ou `--data`). Os diretórios recebem ACL privada para o usuário e SYSTEM; em Linux, modo 0700. JSON é salvo por arquivo temporário, flush, fsync e substituição atômica. O arquivo anterior é preservado se a serialização falhar. Mantenha os arquivos no disco local, não em pasta compartilhada.

Com os aplicativos parados, o administrador pode alterar os JSON. Reinicie após mudanças. Faça backup seguro da pasta da Central, incluindo chave/certificado; o pin precisa permanecer igual para os Agents reconectarem. Regenerar o certificado exige atualizar o pareamento de cada Agent. Proteção DPAPI impede mover a credencial do Agent para outro usuário/máquina simplesmente copiando `agent.json`.

| Arquivo/campo | Finalidade |
| --- | --- |
| `central.json` / `pdvs` | Número, UUID, hash de credencial dos caixas autorizados |
| `central.json` / `host`, `port`, `hostname` | Escuta e endereço de rede local |
| `central.json` / `alarm` | `enabled` e repetição em segundos (dashboard impõe mínimo 10) |
| `central.json` / `dashboard.columns` | Colunas no desktop, de 1 a 8; layout responsivo |
| `central.json` / `supervisors` | Nome, hash de senha e permissão `control` |
| `central.json` / `logs` | `retention_days` e `max_bytes` por arquivo |
| `agent.json` | Número, UUID, Central, porta, pin, token DPAPI e `f11` booleano |
| `central.key`, `central.crt` | Identidade TLS local, protegida por permissões de arquivo |

`add-supervisor` também está no menu da Central e permite usuários somente de visualização. Para revogar um caixa ou supervisor, remova o cadastro correspondente com a Central parada; reiniciar encerra as sessões existentes. Não edite hashes manualmente para criar senhas.

Histórico: `logs/AAAA-MM-DD-NNN.jsonl`, datas UTC. Apenas PDV, horário da solicitação, supervisor, horário do atendimento e resultado de uma lista controlada. O arquivo roda ao atingir `max_bytes`; retenção é aplicada a cada novo registro. Atendimentos iniciados diretamente, sem solicitação F11, não geram histórico. Não há imagens, senhas nem teclas em logs. Não existe garantia de recuperação do atendimento em curso após queda abrupta de energia; estados ficam em memória por definição.

## Validação necessária em Windows antes de produção

A captura e o controle implementados usam o monitor principal e as APIs Windows na sessão do operador. Não abrangem desktop seguro/UAC, tela de login, sessão bloqueada, Ctrl+Alt+Del, IME ou múltiplos monitores. Aplicativos elevados podem bloquear a entrada de um Agent sem elevação. O código não contorna essas restrições do Windows.

Em dois computadores Windows de teste: gerar/instalar ambos os instaladores; confiar no certificado validado; cadastrar e parear; testar F11 global sem foco no Agent, áudio (inclusive repetição com duas pendências), captura, coordenadas com escala de DPI, teclado/layout do operador, tela cheia, alternância e encerramento; desligar a internet mantendo a LAN; reiniciar a Central; desconectar e reconectar o cabo do caixa; verificar logs, retenção, ACL/DPAPI e inicialização após login. Medir carga com o número real de PDVs antes de implantar. Estes testes físicos não foram executados no Linux.
