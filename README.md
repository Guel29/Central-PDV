# Smart PDV Control — Windows 10/11 x64

Dois aplicativos independentes na LAN, sem banco de dados nem serviço externo:

- **SmartPDV-Central-Setup.exe**: instala a Central, que abre diretamente o dashboard HTTPS no navegador do computador administrador, sem login ou cadastro de usuários.
- **SmartPDV-Agent-Setup.exe**: instala o Agent real do caixa. Depois do pareamento, executa sem terminal ou janela na frente do operador e pode iniciar automaticamente após o login Windows.

O computador PDV é cadastrado, mesmo sem contas de usuários na Central. O número do caixa, UUID e credencial individual identificam qual PDV acionou F11. A comunicação usa WebSocket TLS direto com pin SHA-256 do certificado; a remoção do login não removeu o pareamento dos Agents.

## Instalação e primeiro uso

Os builds Windows para testes são publicados em **Releases** do repositório após build e testes bem-sucedidos no GitHub Actions. Baixe os dois `.exe` da mesma versão e confira `SHA256SUMS.txt`. Os instaladores incluem Python e dependências; os computadores de destino não precisam instalar Python ou acessar a internet. Binários ainda sem assinatura Authenticode.

1. Instale a Central no computador administrador. Em **Configuração inicial**, informe seu IP ou nome LAN estável. Não há usuário ou senha do aplicativo.
2. Pelo menu Iniciar, abra **Smart PDV Central > Confiar no certificado local**. O aplicativo confere o fingerprint e solicita confirmação para adicionar o certificado ao armazenamento de confiança do usuário Windows. Não desative verificações TLS.
3. Abra **Cadastrar PDV** para cada caixa, informando um número único. O arquivo de pareamento é salvo em `%LOCALAPPDATA%\SmartPDV\central\pairing\pdv-N.json`; o caminho físico pode variar com Python Microsoft Store durante uso por código-fonte.
4. Transfira o pareamento ao caixa por mídia segura. Instale o Agent e, na configuração inicial, informe o caminho desse arquivo e confirme endereço da Central e número do PDV. A credencial é protegida com DPAPI para aquele usuário Windows. Exclua as cópias de pareamento depois de importar.
5. Inicie a Central. O dashboard abre diretamente; clique **Ativar alarme sonoro** uma vez. No caixa, execute o Agent; mantenha a inicialização automática selecionada no instalador. O operador continua usando o sistema de vendas normalmente.
6. Na Central, permita TCP 8443 somente na rede privada e sub-rede local. Um administrador Windows pode executar:

   ```powershell
   New-NetFirewallRule -DisplayName 'SmartPDV LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -RemoteAddress LocalSubnet -Profile Private
   ```

O dashboard sem senha aceita controle apenas no próprio computador Central (loopback ou conexão originada do endereço local da máquina). Outros computadores LAN podem conectar seus Agents pareados, mas não recebem uma sessão de controle do dashboard. Quem usa a sessão Windows da Central pode operar os caixas; mantenha o computador administrador sob controle da supervisão.

## Operação

F11 global no caixa envia chamado identificado pelo cadastro. O card pisca verde, toca três bipes e repete a cada dez segundos enquanto houver pedidos online. Clique no card para visualizar/controlar a sessão Windows autorizada. Teste mouse, teclado, rolagem, tela cheia, alternância e encerramento. Atendimento ativo é azul; encerramento devolve o card ao amarelo. Offline é cinza e a conexão é refeita automaticamente. A Central pode reiniciar sem exigir que o operador reconfigure o Agent.

O Agent inicia **após o login Windows**, pois precisa do desktop interativo do operador; não roda sobre a tela de login como serviço. Não há janela de operação sobre o caixa. O processo e o atalho permanecem identificáveis no Gerenciador de Tarefas e na pasta Inicializar. Aplicativos elevados/UAC, sessão bloqueada, desktop seguro, Ctrl+Alt+Del, IME e múltiplos monitores não são contornados. A captura usa o monitor principal. Durante controle remoto, operador e supervisor compartilham mouse/teclado da mesma sessão.

## Dados locais

`central.json` guarda PDVs, rede, alarme, dashboard e retenção. `agent.json` guarda número, UUID, Central, porta, fingerprint, token DPAPI e F11 habilitado/desabilitado. Não há cadastro de usuários do aplicativo; campos legados de supervisores em arquivos antigos são ignorados. JSON é escrito por arquivo temporário, flush/fsync e substituição atômica. Diretórios usam ACL para usuário Windows/SYSTEM; o caminho físico é resolvido antes de chamar icacls para compatibilidade com Python Microsoft Store.

Miniaturas e estado ficam em memória; telas e teclas não são gravadas. JPEG de até 320×180 a cada dois segundos, ou 1280×720 a quatro quadros por segundo no atendimento. Logs JSONL diários guardam apenas PDV, solicitação, identificação de atendimento “Central”, horário e resultado controlado; `retention_days` e `max_bytes` configuram retenção/rotação. Preserve a chave e o certificado da Central para manter o pin dos Agents. Reinicie a Central após cadastrar/remover PDVs por configuração.

## Desenvolvimento e testes

Veja [DEVELOPMENT.md](DEVELOPMENT.md) para testar o laboratório sem instalador e o Agent Windows real por código-fonte. O laboratório identifica claramente telas e entrada simuladas. A comunicação TLS é real; a simulação não valida captura ou F11 físicos.

```sh
python3 -m venv /workspace/smartpdv-venv
/workspace/smartpdv-venv/bin/python -m pip install -r requirements-browser.txt
/workspace/smartpdv-venv/bin/python -m pytest -q
/workspace/smartpdv-venv/bin/python tests/development_browser.py
```

Build local dos instaladores: Windows x64, Python 3.12 e Inno Setup 6; execute `powershell -ExecutionPolicy Bypass -File packaging\build.ps1`. O workflow Windows installers executa build, testes nativos, instalação silenciosa de ambos os pacotes, conferência do subsistema GUI sem console e uma requisição HTTPS funcional ao executável Central instalado antes de publicar.

Antes de produção, valide em dois PCs Windows reais: instalação, certificado, ACL/DPAPI, F11 sem foco, áudio com duas pendências, captura/DPI, mouse/teclado/layout, tela cheia, alternância, desconexão/reconexão, reinício da Central, falta de internet mantendo LAN, inicialização após login e carga com o número real de caixas. Os testes automatizados não substituem esse teste físico.

### Agent para Windows 7

Existe um Agent separado em [legacy-agent](legacy-agent/README.md), destinado a **Windows 7 SP1, 32/64 bits, com .NET Framework 4.8**. A workflow `Windows 7 Agent` gera `SmartPDV-Agent-Win7-Setup.exe`. A Central permanece no Windows 10/11. Leia os requisitos e limites de validacao antes do teste no caixa.

### Atualizacao de teclado Windows

Agent Windows 10/11 x64 1.0.1 e Agent legado 0.1.1 usam SendInput com scan codes para a entrada remota (numeros EAN, Enter, modificadores e navegacao). Encerre o Agent e instale a atualizacao na mesma conta Windows. Cadastro e pareamento permanecem no perfil local. Os testes Windows verificam eventos nativos, liberacao de teclas e ABI de entrada. O VRPDV/LS2208 deve ser validado no equipamento de destino; entrada sintetica nao equivale a um leitor USB fisico. Instaladores modernos exigem Windows 10/11 x64; a versao legada publicada destina-se ao Windows 7 SP1 32/64 bits com .NET 4.8. Windows 8/8.1 e ARM nativo nao foram homologados.

### F11 global na Central (1.0.2)

Com o executavel Central em execucao, F11 restaura e traz a janela SmartCentral para frente a partir de outros aplicativos da mesma sessao Windows. Edge/Chrome abrem o dashboard em janela de aplicativo dedicada, identificavel mesmo com outras abas abertas. Se a janela foi fechada, F11 abre novamente; a Central precisa continuar em execucao. O Agent continua usando F11 para chamados apenas no computador PDV. Na Central, F11 passa a ser o atalho global, substituindo o F11 de tela cheia do navegador. Se outro programa ja reservou F11, a Central informa o conflito; nenhum atalho de outro programa e removido. Nao atua na tela bloqueada ou area segura UAC. Em execucao de testes `--no-browser`, nao registra o atalho global.
