# Ponte USB do Smart Controle — Central 1.1.0 / Agent Win7 0.2.0

## Estado desta implementação

Há código integrado de seleção, concessão exclusiva e transporte **binário USB/IP
real por TLS**, mais componente receptor no Agent Windows 7. O transporte foi
exercitado por conexões TCP/WebSocket reais e por um cliente C# compilado.
**Ainda não há uma solução pronta para instalar nos caixas:** falta um pacote de
driver cliente Windows 7 com assinatura de produção aceita, instalação/validação
Windows e o LS2208/VR físicos. Nenhum driver foi carregado nesta tarefa. Não afirmar
que o cartão fiscal funcionará com esta implementação.

A causa da diferença entre leitura no Bloco de Notas e autorização VR continua
sem confirmação. Nenhum teste de digitação/Bloco de Notas precisa ser repetido.
O caminho USB não usa `SendInput`, colagem, texto ou eventos de teclado. O acesso
remoto existente continua separado; não é fallback silencioso do USB.

## Arquitetura e dependências

| Componente | Local/requisito | Licença e instalação |
|---|---|---|
| Central 1.1.0 (`smartpdv/usb.py`, painel existente) | Central Windows 10/11, conforme projeto atual | Código integrado ao repositório; build existente `packaging/build.ps1`. |
| Serviço/driver `usbipd-win` | Central Windows 10/Server 2019 1809+, TCP bruto 3240 **somente local** | GPL-3.0-only. Obter MSI assinado nas [releases oficiais](https://github.com/dorssel/usbipd-win/releases). Não incluído nem presumido instalado. O instalador pode criar regra LAN ampla: o preparo abaixo adiciona bloqueio bruto prevalente. |
| Agent Win7 0.2.0 / `UsbReader.cs` | PDV Windows 7 SP1 x86/x64, .NET Framework 4.8 | Código C# integrado. Executa em segundo plano na sessão do operador, com inicialização no login pelo instalador existente. Não é um novo serviço Windows antes do login. |
| Controlador virtual e `usbip.exe`, `cezanne/usbip-win v0.1.0` | PDV; pacote de driver compatível com arquitetura e assinatura válida | Fonte aberta gratuita, revisão `44063583a5c3e20ec459bddadc9aae37f73bda10`. `LICENSE` GPLv3, com cabeçalhos individuais GPLv2-ou-posterior. Preservar avisos/licenças e obrigações de fonte em redistribuição. **Assinatura de produção não resolvida.** |

O Windows da Central é moderno, conforme o projeto existente; o requisito Windows 7
é atendido pelo código receptor em .NET, não pelo Python 3.12. Não executar o Agent
Python nem o cliente `usbip-win2` moderno no caixa Windows 7.

O [README oficial v0.1.0](https://github.com/cezanne/usbip-win/blob/v0.1.0/README.md)
usa certificados de teste e declara não estar pronto para produção. Essa instalação
**não foi adotada**. Não há comandos para TESTSIGNING, desativação de integridade ou
instalação do PFX de teste nos helpers. Uso próprio não elimina a assinatura do
kernel. [Preparação/build/verificação do driver](../tools/usb-win7/README.md).
Não é um driver próprio novo; reutiliza-se uma dependência existente e separada.

## Funcionamento e proteção

A Central aceita USB apenas pelo dashboard local e pelo dono de um atendimento
ativo. O PDV precisa estar cadastrado, autenticado pela credencial individual já
pareada e anunciar capacidade USB depois da instalação aprovada. Cada conexão usa
um token de concessão efêmero, de uso único, limitado ao PDV e à identidade exata
selecionada. A conexão USB abre outro WebSocket TLS na **mesma porta da Central**,
com pin SHA-256 no cliente gerenciado compatível com Windows 7.

Somente a mensagem de importação do BUSID concedido é aceita. Não há proxy TCP de
destino arbitrário nem listagem remota de todos os USB. A Central consulta a
identidade antes e depois de importar e confere BUSID/VID/PID na resposta USB/IP;
com isso, não encaminha a resposta de outro dispositivo ao cliente. Na sequência,
os pacotes são opacos, com blocos até 64 KiB e pressão de fluxo. Não são gravados,
interpretados como códigos, enfileirados em disco ou repetidos após falha.

O Agent inicia `usbip.exe` apontando para uma porta **loopback efêmera**, aceita
uma conexão local, valida o preâmbulo e encaminha os bytes pelo túnel. Não oferece
listener USB na LAN. Só informa conectado quando o transporte foi importado e o
Windows reportou um novo dispositivo PnP correspondente sem erro. Isso não é
comprovação de compatibilidade VR. Saídas/diagnósticos do componente são descartados,
sem logs de URB, cartões, senhas ou hashes de leituras.

Trocar destino fecha a concessão anterior e aguarda o serviço USB informar que o
cliente anterior foi liberado. Não reconecta USB automaticamente nem muda PDV.
Encerrar atendimento, perder dashboard/Agent/túnel, expirar sessão, retirar leitor
ou falhar a verificação de firewall revoga a concessão. Reiniciar os processos
restaura o pareamento e seleção, mas **não** a conexão USB anterior. Buffers são
apenas da sessão viva; comportamento de buffers do driver/dispositivo depende de
validação física. Nenhuma configuração da autorização VR é modificada.

A porta 3240 não pode ser exposta na LAN/internet. `WindowsHost.secure` verifica a
regra efetiva de bloqueio e os perfis do Firewall antes e durante uma concessão.
Não criar redirecionamento de portas no roteador nem desabilitar o Firewall.
GPO/antivírus/firewall de terceiros podem exigir validação adicional local.

## Compilar os aplicativos

Na Central, usar o build existente em Windows com Python 3.12, PyInstaller e Inno
Setup conforme README do projeto. As dependências Python/lockfiles não mudaram.

Agent Win7 em computador de build Windows com MSBuild/referências .NET 4.8:

```powershell
.\scripts\usb\build-agent.ps1 -MSBuild 'CAMINHO_REAL\MSBuild.exe' -InnoSetup 'CAMINHO_REAL\ISCC.exe'
```

O Inno Setup precisa ser a versão compatível com Windows 7 usada no CI (6.2.2).
`-InnoSetup` é opcional se desejar apenas o executável. O build também produz um
probe de transporte sem desktop/driver. O Agent pode ser compilado x86 e receber
um driver nativo x86 ou x64 conforme o SO. **Não confundir o EXE do Agent com o
controlador virtual SYS/CAT.** O instalador do Agent não inclui o driver USB.

## Preparar a Central

1. Instalar o serviço oficial `usbipd-win`, conferindo sua assinatura e licença.
2. Conectar o LS2208 e abrir o painel atualizado. Clicar **Listar dispositivos USB**.
   Os demais dispositivos aparecem na lista, mas somente candidatos Symbol/Motorola
   podem ser selecionados. O VID 05E0 sozinho não comprova que o modelo é LS2208.
3. Identificar pela etiqueta física e pelo PnP InstanceId exato. Não escolher outro
   teclado, hub ou dispositivo por aproximação. Informar esse ID ao preparo abaixo.
4. Em PowerShell administrador, usando os **IPs reais fixos/reservados** dos PDVs:

```powershell
.\scripts\usb\central.ps1 -ReaderInstanceId 'IDENTIDADE_PNP_REAL' -PdvAddresses '192.168.1.21','192.168.1.22' -CentralPort 8443
```

O script bloqueia TCP 3240 de entrada em todos os perfis e permite somente os IPs
informados na porta TLS, perfis Privado/Domínio. Faz `bind` apenas do dispositivo
exato. Regras anteriores de outros aplicativos não são apagadas. Se existirem
regras amplas para a porta da Central, revisá-las com o administrador: uma nova
regra restrita não estreita regras antigas. O script não altera perfis de rede.

O `bind` persiste após reinício; a **conexão** não. Ao desconectar no aplicativo,
o host deixa de enviar o leitor ao PDV e ele pode voltar ao uso local, mesmo
continuando preparado/compartilhado no serviço. Remover compartilhamento é uma
operação administrativa separada.

## Preparar cada PDV — bloqueado até existir pacote assinado

Não executar as etapas de instalação abaixo com saída não assinada do build.
Elas são instruções implementadas para o pacote futuro legitimamente assinado,
ainda não disponível nesta entrega.

1. Instalar/atualizar Agent Win7 0.2.0; manter o pareamento existente. Para novo PDV,
   usar **Cadastrar PDV** no Menu Iniciar da Central, transferir JSON por meio seguro
   e importar pelo assistente do Agent. Remover cópias do JSON depois. Token fica em
   DPAPI do usuário e pasta com ACL. Reemitir pareamento revoga a credencial antiga.
2. Obter pacote assinado e revisado do cliente contendo `usbip.exe`, `usb.ids`,
   `usbip_vhci.inf/.sys/.cat`, `LICENSE`. O hash esperado do EXE deve vir do build
   revisado; não aceitar hash fornecido junto a um binário desconhecido como prova.
3. Executar no PDV como administrador, com SignTool e DevCon oficiais compatíveis instalados:

```powershell
.\scripts\usb\install-pdv.ps1 -Package 'C:\pacote-assinado' -SignTool 'CAMINHO_REAL\signtool.exe' -DevCon 'CAMINHO_REAL\devcon.exe' -ExpectedExeSha256 'SHA256_DO_EXE_REVISADO'
```

O helper exige assinatura kernel e pertencimento SYS/INF ao CAT, confere hash do
EXE, usa DevCon Microsoft com o hardware ID exato `root\usbip_vhci` e protege `%ProgramData%\SmartPDV-USB\Client` para gravação por Administradores
ou SYSTEM, leitura/execução pelos usuários. Não substitui controlador USB/IP já
existente e não habilita componente se a instalação não for confirmada.
O DevCon deve corresponder à arquitetura do SO. O instalador legado upstream
   contém caminho de instalação hardcoded para amd64; o helper usa DevCon em vez
   desse caminho para também preparar x86. Reverificar arquitetura, cadeia e atualizações de confiança no Windows 7 real.
Falhas não habilitam testes de assinatura nem ignoram verificações.
4. Reiniciar o Agent. A capacidade USB só é anunciada com aprovação instalada e hash
   correspondente. Não executar duas instâncias/versões do Agent no mesmo caixa.
   O início automático existente ocorre **ao entrar no usuário**, não antes do login.
   Serviço PDV independente antes do login não foi implementado nesta versão.

## Operação após preparar os componentes

1. Na Central, atualizar lista e **Selecionar LS2208**. Confirmar fisicamente o modelo
   e a identidade. A seleção é persistida em `usb-reader.json`, separado dos PDVs.
2. Abrir o card do PDV de destino. O atendimento deve pertencer à mesma aba.
3. Clicar **Conectar leitor ao PDV**. Aceitar o aviso de indisponibilidade local.
   A interface mostra disponível, conectando, conectado, desconectado ou erro a
   partir da enumeração, concessão, importação e confirmação PnP reais.
4. Para trocar, encerrar/alternar atendimento para o outro PDV e clicar conectar.
   O backend também fecha/aguarda a conexão antiga antes de conceder a nova.
5. **Desconectar leitor** ou encerrar atendimento. Após queda/reinício/retirada,
   corrigir o problema e solicitar uma nova conexão explicitamente. Leituras não
   são reapresentadas pelo aplicativo.

Conectar fica desabilitado se o Agent não anunciou o componente USB. Sem driver
válido, não há conexão a testar no VR: os botões não simulam êxito.

## Desinstalação e reversão

- Desconectar leitor e encerrar Agent antes da remoção. No PDV, com o DevCon
  **oficial assinado Microsoft**, arquitetura correta, disponível no WDK:

```powershell
.\scripts\usb\remove-pdv.ps1 -DevCon 'CAMINHO_REAL\devcon.exe'
```

  O helper remove somente a identidade de controlador e INF registrados por esta
  instalação; não remove driver arbitrário. Preserva binários/licença para inspeção
  e informa a pasta para remoção manual. Nenhuma regra de firewall é criada no PDV.
  Remover Agent por Programas e Recursos também remove o acesso remoto, portanto
  é opcional; para preservar acesso remoto, remover apenas a aprovação/driver USB.
- Na Central, com conexão encerrada, administrador:

```powershell
.\scripts\usb\central.ps1 -Action Remove -ReaderInstanceId 'IDENTIDADE_PNP_REAL'
```

  Faz unbind da identidade exata, usando GUID persistido quando disponível (inclusive leitor retirado). Só remove o bloqueio bruto se não houver outros USB
  compartilhados; caso contrário mantém proteção e informa o impedimento. Remove
  somente as regras `SmartPDV-USB-*` próprias. Desinstalar `usbipd-win` por Aplicativos
  quando não houver outro uso; seu desinstalador remove os componentes do fornecedor.
  Não apagar certificados/pareamentos existentes do Smart Controle.

## Verificação realizada e aceitação pendente

Ver [relatório de execução](usb-validation-report.md). O endpoint de teste TCP
confere framing e transporte; não emula LS2208, driver kernel nem o VR. Não foram
solicitados novos testes de digitação ou Bloco de Notas.

Após resolver o driver e instalar em laboratório físico: verificar dispositivo no
Gerenciador de Dispositivos do PDV, concluir autorização com cartão fiscal válido
na tela atual do VR e confirmar rejeição normal de cartão não autorizado; testar
uso exclusivo, devolução à Central, dois destinos, queda de rede, retirada, reinício
e limpeza de dispositivo virtual. Não registrar os códigos dos cartões. Nenhuma
mudança de senha ou contorno das regras do VR é necessário/autorizado.
