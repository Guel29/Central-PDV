# Teste do leitor — Central 1.0.10 / Agent Win7 0.1.7

**Resultado informado pelo usuário:** a leitura fiscal continuou falhando no
teste com a atualização atual, após a entrega da Central 1.0.11. A preservação
de cadência não resolveu o problema nesse teste. Não apresentar os testes
automatizados abaixo como homologação de cartão fiscal nem solicitar novamente
o mesmo teste como se houvesse outro mecanismo de entrada. A versão 1.0.11
acrescentou recuperação de pareamento, mantendo o motor de leitura anterior.

O relato não identifica a API utilizada pela VR. Veja o
[estado da investigação e a informação técnica que falta](leitura-fiscal-pendente.md).

## Análise

O teclado remoto usa eventos DOM, WSS/TLS na LAN e `SendInput` por scan codes
(Python/ctypes no Windows moderno; C#/.NET 4.8 no Win7 SP1). Não apresenta USB
ao PDV. O código acrescentava no mínimo 20 ms por pressão e transmitia cada
transição separadamente, alterando a cadência do leitor.

Essa perda de cadência foi confirmada no código; **a causa da rejeição pelo
VRPDV continua desconhecida**. Pode envolver cadência, Raw Input/HID, dispositivo
ou outro mecanismo. Os relatórios anteriores não continham eventos e não
identificam a API da VR. A versão 0.1.6 informada era do SmartPDV, não da VR.

Esta é uma tentativa de compatibilidade com os equipamentos atuais, gratuita e
sem driver. Preserva intervalos observados pelo navegador. Não é USB direto nem
correção homologada do cartão fiscal. `SendInput` continua marcado como entrada
injetada. A VR e sua validação permanecem intactas.

## Alterações e riscos

- `smartpdv/web/timed-keys.js`, `app.js`, `index.html`: captura temporária de
  números, código físico e intervalos, sem campo EAN ou botão de autorização.
- `smartpdv/central.py`, `agent.py`, `timed_keys.py`: capacidade anunciada pelo
  Agent e validação pelo mesmo canal TLS, dono do atendimento e permissão de
  teclado. Agents antigos continuam no caminho individual.
- `smartpdv/windows.py`, `windows_keyboard.py`, `legacy-agent/Agent.cs`,
  `ScanKeyboard.cs`, `TimedKeys.cs` e projeto: reprodução dos intervalos sem o
  mínimo artificial de 20 ms nesse caminho. Teclado individual mantém seu mínimo.

Rajadas: pelo menos quatro dígitos, até 64 transições e 250 ms observados, sem
modificadores, repetição ou sobreposição de teclas. Pausas de 35 ms encerram a
captura; sequências não qualificadas seguem pelo caminho individual. Preserva
zeros e Enter principal/numérico observado; não inventa sufixos nem acelera os
intervalos recebidos. Números digitados devagar podem aguardar até 35 ms antes
do envio. O navegador não identifica qual dispositivo USB originou a leitura.

Troca/encerramento, perda de foco/conexão ou desativação do teclado descartam a
captura pendente. Um pacote já recebido termina antes do próximo comando:
encerrar pode aguardar até 250 ms de intervalos solicitados, além de atrasos do
Windows. Falhas tentam soltar as teclas; reconexão não repete leituras.

Dados existem apenas em memória no caminho do teclado remoto; não são gravados,
resumidos por hash ou incluídos em erros. No Win7 a resolução do temporizador é
solicitada apenas durante a rajada e restaurada em `finally`. Navegador e Windows
podem adicionar atrasos: não há garantia de tempo real nem tráfego USB original.

Preserva acesso direto e pareamento. Não adiciona autenticação individual: a
sessão local depende do acesso à conta Windows. Isso não cumpre o requisito
separado de identificar supervisores individualmente numa conta compartilhada.

## Teste no equipamento real

1. Guarde os instaladores anteriores para retorno. Encerre Central e Agent
   antes de atualizar. Preserve JSONs e pareamento.
2. Instale Central **1.0.10** no supervisor e Agent **0.1.7** no PDV Win7 SP1
   com .NET 4.8. No PDV Windows 10/11 x64, use Agent **1.0.10**.
3. Reabra aplicativos/dashboard e confira a versão do **Agent conectado** no
   card; a instância antiga não pode continuar aberta.
4. Com LS2208 na Central e imagem remota em foco, leia primeiro um **produto
   de teste**, sem concluir venda, e confira EAN e Enter.
5. Abra a operação fiscal da VR, selecione seu campo pela imagem remota e leia
   **uma vez** o cartão autorizado na Central. A VR precisa validar normalmente
   o cartão e as permissões. Não habilite senha, cole o código ou reconfigure o leitor.
6. Confirme que a VR continua exigindo cartão. Teste também teclado, mouse,
   F11, troca de PDV, encerramento e reconexão.
7. Informe somente versões e se EAN/cartão funcionaram. Não envie cartão,
   credenciais ou capturas do código. Não use cartão fiscal em Bloco de Notas,
   console, capturas de rede ou relatórios.

Se continuar falhando, a tentativa **não resolveu o problema**. Não reduzir
proteções nem tratar como permissão comprovada. Será necessário identificar o
mecanismo da VR/obter orientação compatível. Não foi confirmado redirecionador
USB gratuito com driver de produção confiável para Win7 e equipamentos atuais.

## Verificação

Python/JavaScript testam dados fictícios, ordem, zeros, intervalos, validação,
permissões e cancelamento. Chromium verifica captura/transporte WSS com Agent de
teste e caminho antigo. Probes Windows verificam entrada nativa, marca de
injeção e retirada do mínimo de 20 ms; o .NET é testado após instalação com TLS
e rejeição de certificado incorreto. Não incluem VRPDV, cartão real, LS2208 físico
ou máquina física Windows 7.

Verificações desta atualização: 69 testes Python passaram no Linux (3 nativos
Windows ignorados), testes JavaScript e dois roteiros Chromium passaram. O
[build Windows moderno](https://github.com/Guel29/Central-PDV/actions/runs/39684467776)
e o [build do Agent .NET](https://github.com/Guel29/Central-PDV/actions/runs/39684467727)
passaram, incluindo testes nativos e instalados em Windows moderno.
Os três instaladores publicados foram baixados e seus SHA-256 conferidos contra
os manifestos das respectivas publicações.
