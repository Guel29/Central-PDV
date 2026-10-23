# Relatório da implementação USB — 23/10/2026

Repositório `Guel29/Central-PDV`, HEAD inicial
`e761d1b2964ef178ceb6da5419cc25250fbae329`. Alterações locais; sem push/publicação.

## Implementado

- `smartpdv/usb.py`: enumeração usbipd, seleção persistente por identidade exata,
  confirmação do modelo, concessão exclusiva vinculada a atendimento/PDV/dono,
  proteção de importação USB/IP e túnel binário autenticado na porta TLS existente.
- Encerramento e revogação por fechamento do atendimento/dashboard/Agent, expiração,
  falha/retirada do leitor; troca de destino aguarda liberação real do servidor.
- `legacy-agent/UsbReader.cs`: cliente gerenciado Windows 7/.NET 4.8, socket local
  efêmero e processo USB/IP real, confirmação PnP e encerramento sem reanexação
  automática. Sem APIs de teclado no caminho USB.
- `LocalWebSocket`: framing binário compatível com Windows 7 sem websocket.dll,
  preservando pin SHA-256 e autenticação individual existentes.
- Painel integrado aos cards/atendimentos, com lista, seleção, aviso, conectar,
  desconectar e estados vindos do backend/cliente. Controle remoto/alertas preservados.
- Helpers de build, instalação condicionada a assinatura, bloqueio da porta bruta,
  regras LAN limitadas e remoção específica. Documentação de ambos os computadores.
- Versões Central 1.1.0 e Agent Win7 0.2.0; CI ajustado para compilar novo componente
  e executar o probe de transporte C#. O CI remoto não foi disparado nesta tarefa.

## Compilado e executado neste ambiente

| Verificação | Resultado |
|---|---|
| Dependências Python com constraints/lockfiles existentes | Instaladas em `.venv`; manifestos e lockfiles inalterados. |
| Preparação da fonte externa Windows 7 | 127 arquivos exportados do commit fixado; hashes conferidos. Não são binários de driver. |
| Compilação C# do Agent Win7 0.2.0 | Executada com Mono 6.12, linguagem C# 5, x86; gerado `build/SmartPDV-Agent-Win7.exe` e config. Compilação em Linux não prova execução Windows. |
| Compilação C# do `UsbTransportProbe` | Executada com o mesmo código de TLS/WebSocket do Agent, sem desktop/driver. |
| `tests/usb_legacy_transport.py` + probe C# compilado | Aprovado: TLS com pin, autenticação, importação USB/IP e ida/volta de bloco binário de 64 KiB contra Central e endpoint TCP controlado. |
| `tests/browser_smoke.py` / Chromium | Aprovado: entrada direta, cards, alertas, atendimento, controle remoto e reconexão; sem erros JS. Não é teste físico de leitura fiscal. |
| `tests/usb_browser.py` / Chromium | Aprovado: enumeração/seleção, concessão/importação real contra endpoint TCP controlado, confirmação e desconexão; sem erros JS. |
| Suíte pytest | Resultado final registrado abaixo; testes USB exercitam autenticação, uso único, exclusividade/troca, expiração/dono, dispositivo diferente, firewall ausente e perda de identidade. |
| `git diff --check` | Aprovado. |

O teste C# encontrou um erro real no limite de mensagens de 64 KiB, corrigido e
retestado. Os fixtures USB dos testes **não são dispositivos reais**; os estados de
PnP são mensagens de cliente controladas nos testes, não Windows sendo executado.
Não foram gravados códigos de cartões, pacotes reais de leitor ou capturas HID.

Mono foi obtido por pacotes Debian com metadados assinados/verificações APT
preservados e extraído somente em `/workspace/scratch/mono`. Não foi necessário
administrador nem alteração de pacotes do sistema. Não foi desabilitado TLS.

## Não executado / limitações materiais

- Build Windows MSBuild/.NET Framework, PyInstaller Windows e Inno Setup:
  não executados; sem host Windows nesta tarefa. Não há instaladores Windows novos
  gerados nem assinatura Authenticode do EXE de desenvolvimento.
- Build kernel SDK/WDK e assinatura de produção do controlador Windows 7:
  **pendentes e bloqueantes para uso real**. Nenhum SYS/CAT novo produzido/instalado.
- Scripts PowerShell/DevCon/SignTool, regras efetivas Windows Firewall e instalação/
  remoção em Windows: escritos e revisados, **não executados** neste executor Linux.
- PnP real, driver receptor Windows 7, interoperabilidade entre drivers usbipd-win
  e usbip-win v0.1.0, arquitetura x86/x64 do caixa e cadeia de confiança: pendentes.
- Inicialização do Agent ocorre no login do operador pelo instalador existente.
  Serviço receptor independente antes do login não foi implementado. Serviço USB
  host é dependência externa; nenhum serviço de kernel próprio foi escrito.
- Retirada/reconexão, limpeza do controlador virtual após encerramento forçado,
  perda física da LAN, reinício real e comportamento de buffers do leitor/kernel:
  pendentes de hardware. O código não mantém fila persistente nem repete tráfego.
- Reconhecimento físico do LS2208 no PDV e autorização real de cartão na tela atual
  do VR: **pendentes; nenhuma compatibilidade afirmada**. Regra fiscal inalterada.

Não foi solicitado ao usuário repetir digitação/Bloco de Notas. A entrega é uma
implementação do aplicativo em desenvolvimento, **não um produto instalado/pronto
para resolver a autorização fiscal**. O próximo pré-requisito externo continua
sendo o driver de produção válido para Windows 7; depois são necessárias instalação
Windows e validação física. Nenhuma autorização pessoal substitui esse requisito.

Resultado final: **86 testes aprovados e 3 ignorados** em pytest. Os ignorados são
hotkey/janela Windows, entrada nativa Windows e ACL/DPAPI nativos. `pip check` sem
dependências quebradas. Os testes de navegador e probe C# descritos acima também
concluíram com saída 0. O pacote de desenvolvimento é uma cópia revisável das fontes
atuais mais o EXE gerenciado compilado; não inclui driver USB nem instalador pronto.
