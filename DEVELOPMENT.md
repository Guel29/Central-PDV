# Testar a Central e o Agent antes de gerar instaladores

Este modo não gera instaladores. Ele usa o mesmo dashboard, autenticação, alarmes e protocolo HTTPS/WebSocket da aplicação. A Central e **dois Agents** executam simultaneamente, comunicando-se por TCP/IP em loopback. Um único processo de laboratório orquestra a Central e os Agents como tarefas independentes conectadas pelo protocolo real; não são dois executáveis Windows. Uma segunda aba oferece o painel do operador. Não há banco nem serviço externo.

**O laboratório simula o desktop do caixa, o F11, o mouse e o teclado do Windows.** A tela sintética diz “DESKTOP SIMULADO”. O envio das mensagens, a autenticação, o TLS, o pareamento, os estados, os logs e o dashboard são reais. O modo de produção continua usando `windows.Desktop` e não foi substituído por simulação.

## Prévia no ChatGPT

O conjunto de ferramentas deste ambiente não oferece publicação de uma porta HTTP/TLS nem uma prévia lateral interativa. Um servidor iniciado na máquina do Codex não fica acessível pelo navegador do seu computador através de um endereço loopback. Capturas nesta conversa não são uma sessão interativa. Portanto, aqui validamos com Chromium automatizado; para você clicar e testar em tempo real, execute localmente seguindo os passos abaixo.

## Windows — um comando para iniciar

1. Instale Python **3.12 x64** (marque a instalação do launcher `py`). Baixe a versão atual do repositório e extraia o ZIP.
2. Abra PowerShell **na pasta que contém `requirements.txt`**.
3. Execute:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -TrustLocalCertificate
   ```

O script cria `.venv`, instala as dependências, solicita uma senha de laboratório com pelo menos 12 caracteres e prepara dados em `%LOCALAPPDATA%\SmartPDV\development`, separados dos dados reais. O parâmetro explícito `-TrustLocalCertificate` importa **somente o certificado local gerado pelo laboratório** para o armazenamento de confiança do usuário atual, depois de comparar seu fingerprint SHA-256 com a configuração local. Não desativa verificações TLS. A confiança é necessária para HTTPS e WSS funcionarem normalmente no navegador.

O navegador abre na Central local, porta 8443. Use preferencialmente Edge ou Chrome, que utilizam a confiança configurada no Windows. Entre com:

- Usuário: `desenvolvimento`
- Senha: a escolhida na primeira execução; não há senha padrão.

Clique **Abrir Agent simulado** no banner para abrir a segunda aba. Coloque as duas janelas lado a lado, por exemplo com Windows+Seta. A aba Central representa o administrador; a aba Agent representa o operador e mostra os dois caixas simulados.

Se preferir gerenciar confiança manualmente, omita `-TrustLocalCertificate`, valide o certificado local e importe-o antes de usar o navegador. O arquivo e o fingerprint são informados no terminal. Não ignore avisos de certificado e não desative TLS.

**Pare com Ctrl+C no PowerShell.** Se a porta 8443 estiver ocupada, pare a outra Central que você iniciou; não encerre processos desconhecidos. Reinicie com o mesmo comando; senha e identidade TLS de desenvolvimento são preservadas.

## Roteiro dos botões e funcionalidades

1. Na Central, clique **Ativar alarme sonoro**. O navegador precisa dessa interação; mantenha o volume ligado.
2. No painel Agent, em PDV 1, clique **Solicitar liberação (F11)**. O card da Central pisca verde e emite três bipes. Aguarde dez segundos para testar repetição. O atalho F11 é apenas local à página e pode ser reservado para tela cheia pelo navegador; o botão sempre está disponível. O F11 global real exige o Agent Windows.
3. Solicite também no PDV 2. Atenda o PDV 1 clicando no card; o PDV 2 permanece pendente e o alarme continua.
4. A tela remota sintética abre. Clique na imagem e digite: o texto aparece na imagem e no painel Agent, após passar pelo protocolo real. **Enter** ou um clique no botão **LIBERAR TESTE** da imagem marca a venda sintética como liberada. Isso não executa liberação em nenhum software de caixa real.
5. Teste **Tela cheia**, **Alternar PDV** e **Encerrar atendimento**. Quando não houver pedidos pendentes online, as próximas repetições do alarme cessam. Os cards atendidos voltam ao amarelo. Use **Sair** para testar logout.
6. No painel Agent, **Desconectar** cancela a tarefa daquele Agent e fecha sua conexão WebSocket real. O card fica cinza. **Reconectar** inicia novamente o Agent e o card online retorna; o outro PDV continua funcionando.
7. **Limpar venda simulada** limpa o texto e a liberação sintéticos, sem alterar estados de atendimento ou encerrar a sessão.
8. Feche só a aba Central durante atendimento: a conexão do supervisor encerra o atendimento. Reabra a Central para conferir o estado.

Os comandos do painel são autenticados, protegidos por Origin e existem **somente** no módulo de desenvolvimento. O laboratório escuta apenas em `127.0.0.1`, sem exposição para a LAN ou internet. Não utiliza dados nem credenciais de produção. Como representa dois caixas no mesmo computador, não mede latência ou estabilidade de uma rede física.

## Atualizar a interface durante o desenvolvimento

- Editar HTML, CSS ou JavaScript em `smartpdv/web` recarrega automaticamente as duas abas em aproximadamente 1,5 segundo. O login é restaurado pelo cookie seguro, sem armazenar senha no navegador. Sessões de controle são encerradas e devem ser abertas novamente após a atualização.
- Mudanças em Python exigem Ctrl+C e executar novamente o comando. As sessões autenticadas antigas expiram com o processo; entre novamente. O certificado e o cadastro do laboratório persistem.
- Para atualizar o código vindo do GitHub: com o servidor parado, use `git pull --ff-only` se você usa Git e não tem edições locais; ou extraia o novo ZIP em outra pasta. Não sobrescreva suas alterações sem guardá-las. Dados de desenvolvimento ficam fora do projeto.
- Se esquecer a senha, pare o laboratório e mova a pasta **development** para um backup privado antes de configurar um novo laboratório. A nova identidade TLS exige importar e conferir o novo certificado. Nunca faça isso nas pastas `central` ou `agent` de produção.
- Para remover a confiança de teste depois: abra `certmgr.msc`, localize o certificado `127.0.0.1` do laboratório em Autoridades de Certificação Raiz Confiáveis, confira a identidade e remova somente esse certificado.

## Executar manualmente em Linux ou Windows

```sh
python -m pip install -r requirements.txt
python -m smartpdv.dev --prepare
python -m smartpdv.dev --open
```

Use Python 3.12 dentro de um ambiente virtual. `--data DIRETORIO` escolhe uma pasta exclusiva de laboratório; não aponte para configurações reais. No Linux, a confiança deve ser configurada no armazenamento do navegador usando o certificado verificado. `--open` abre o navegador do computador onde o comando é executado, não o navegador remoto do usuário do ChatGPT.

## Testar Windows real e dois computadores na LAN

Não use `smartpdv.dev` para validar captura, hotkey global ou entrada física. Instale as dependências em ambos os computadores Windows e use a CLI real, sem instaladores:

```powershell
# Computador administrador, na pasta do projeto
.\.venv\Scripts\python.exe -m smartpdv central setup
.\.venv\Scripts\python.exe -m smartpdv central add-pdv
.\.venv\Scripts\python.exe -m smartpdv central

# Computador operador, depois de receber o pareamento por meio seguro
.\.venv\Scripts\python.exe -m smartpdv agent setup
.\.venv\Scripts\python.exe -m smartpdv agent
```

A preparação do ambiente virtual em cada máquina é `py -3.12 -m venv .venv` e `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Use o IP/nome LAN real da Central na configuração. Confira o certificado e permita TCP 8443 somente da sub-rede privada na Central, conforme README.md. Cadastre antes de iniciar/reinicie após cadastrar. Remova o arquivo de pareamento transferido depois da importação. O Agent deve rodar no Windows interativo do operador. O dashboard pode ser aberto no navegador da Central usando seu endereço de rede.

Nesse fluxo, F11 global, captura do monitor principal, mouse, teclado e rolagem são implementações Windows reais, sujeitas a UAC, sessão bloqueada, privilégios e layout do teclado. Esses recursos precisam de teste físico em Windows e **não foram validados no ambiente Linux do Codex**. Para validar reconexão da Central real, reinicie-a mantendo o Agent em execução. Teste também desligar somente a internet mantendo a LAN ativa.

## Validação automatizada do laboratório

```sh
python -m pip install -r requirements-browser.txt
python -m pytest -q
python tests/development_browser.py
```

O teste do navegador requer Chromium (`CHROMIUM_PATH` pode apontar para o executável). Ele abre as duas abas, testa dois Agents, chamados, encaminhamento de teclado, liberação sintética, alternância, tela cheia, desconexão, reconexão, limpeza, recarga automática e manutenção do login. Confia apenas na chave do certificado temporário por pin SPKI. Não gera instaladores nem acessa serviços de produção.
