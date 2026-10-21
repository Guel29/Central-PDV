# Periféricos autorizados pela SmartCentral

A decisão de permitir entrada remota fica na Central, em `central.json`:

```json
"peripherals": {"keyboard": true, "scanner": true, "mouse": true}
```

Use o painel **Autorizações de entrada — SmartCentral** para salvar essas opções. O Agent recebe os comandos autorizados durante o atendimento que pertence à sessão da Central. A autenticação dos computadores e a criptografia TLS permanecem necessárias para identificar os equipamentos da LAN.

## Implementado

- Teclado: comandos enviados pela imagem remota, incluindo um leitor USB que se apresenta ao Windows como teclado.
- Mouse: movimento, botões e rolagem na imagem remota.
- Leitor: campo EAN dedicado na Central, com 1 a 32 dígitos, zeros iniciais e Enter. Essa autorização é independente do teclado da imagem remota. Configure o leitor em modo teclado com Enter ao final.
- Revogação: teclado e mouse desativados são bloqueados pelo servidor, e as teclas/botões já pressionados são liberados. A liberação também é permitida com os controles desativados.
- Persistência: gravação atômica em JSON local. Em caso de falha ao salvar, as opções anteriores continuam aplicadas. Sem banco de dados e sem EAN em logs.

O navegador recebe teclas; ele não identifica se vieram de um teclado ou do LS2208, nem de qual porta USB. O campo EAN separa a leitura pelo destino na interface. A permissão não é uma lista de dispositivos físicos e não altera permissões do Windows no computador remoto.

## Teclas físicas (Central 1.0.6 / Agent legado 0.1.5)

O usuário delimitou o escopo a LS2208 em modo teclado, teclado e mouse. O projeto trata essas entradas pelo controle remoto existente.

O dashboard passa a enviar `KeyboardEvent.code` junto de `key`. Antes, tanto `Digit1` quanto `Numpad1` viravam o caractere `1`, reinterpretado pelo Agent como a tecla da fileira superior. Agora os Agents preservam os scan codes físicos correspondentes, incluindo Enter do teclado numérico e os lados dos modificadores. O botão **Windows no PDV** envia a tecla Windows ao computador remoto sem depender de capturar o atalho local do navegador.

O campo EAN preserva a identificação física dos dígitos quando a leitura é digitada continuamente no fim do campo e termina em Enter. Uma colagem ou edição manual utiliza o encaminhamento anterior por caracteres. Códigos e identificação de teclas continuam apenas em memória/trânsito. Central e Agent antigos continuam usando o formato anterior; atualize ambos para testar a preservação física.

O estado Num Lock/Caps Lock pertence ao Windows de cada computador e ainda não é sincronizado automaticamente. Para o teclado numérico, confira Num Lock nos dois computadores. Preservar scan codes não cria um dispositivo USB no PDV, nem garante que o VRPDV consuma entrada sintetizada. O teste com VRPDV/LS2208 real continua necessário.

Os testes incluem eventos de teclado gerados pelo navegador, transporte TLS, distinção de scan codes reais por hooks Windows nos dois Agents e liberação de modificadores. O hook existe somente nos executáveis/testes de CI.

## Compartilhamento USB completo: pendente

Fazer o PDV enxergar um USB conectado à Central como um dispositivo local requer captura de requisições USB na Central, transporte autenticado/criptografado pela LAN e um controlador USB virtual/driver no PDV, com suporte ao Windows e ao dispositivo. O uso do dispositivo na Central pode precisar ser exclusivo durante o compartilhamento.

Esses componentes ainda não existem neste projeto. As opções atuais não habilitam impressoras, balanças, pinpads, pendrives ou qualquer USB genérico. Também não há enumeração de dispositivos, seleção por VID/PID, instalação de driver ou homologação desse mecanismo para Windows 7/10/11. Um futuro componente nativo precisará de drivers devidamente assinados e testes físicos nessas versões; uma caixa de seleção no dashboard não fornece esse mecanismo.

## Compatibilidade com VRPDV

Os Agents continuam usando `SendInput` com scan codes. O campo EAN utiliza o mesmo caminho de entrada nativa existente, sem nova integração com o VRPDV. O retorno positivo dessa API confirma inserção no fluxo de entrada do Windows, sem comprovar consumo pelo aplicativo.

O usuário confirmou que a leitura funciona no VRPDV localmente e pelo AnyDesk instalado, mas falha pelo SmartPDV. Essa falha permanece em investigação. Os testes automatizados cobrem o transporte, as autorizações, a ordem dos dígitos e os eventos nativos Windows; não incluem o leitor físico nem o VRPDV.

Atualização: Central/Agent Windows 10/11 x64 1.0.6 e Agent Windows 7 SP1/.NET 4.8 0.1.5. Encerre os aplicativos antes de atualizar e use a mesma conta Windows para preservar o pareamento existente.
