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

## Compartilhamento USB completo: pendente

Fazer o PDV enxergar um USB conectado à Central como um dispositivo local requer captura de requisições USB na Central, transporte autenticado/criptografado pela LAN e um controlador USB virtual/driver no PDV, com suporte ao Windows e ao dispositivo. O uso do dispositivo na Central pode precisar ser exclusivo durante o compartilhamento.

Esses componentes ainda não existem neste projeto. As opções atuais não habilitam impressoras, balanças, pinpads, pendrives ou qualquer USB genérico. Também não há enumeração de dispositivos, seleção por VID/PID, instalação de driver ou homologação desse mecanismo para Windows 7/10/11. Um futuro componente nativo precisará de drivers devidamente assinados e testes físicos nessas versões; uma caixa de seleção no dashboard não fornece esse mecanismo.

## Compatibilidade com VRPDV

Os Agents continuam usando `SendInput` com scan codes. O campo EAN utiliza o mesmo caminho de entrada nativa existente, sem nova integração com o VRPDV. O retorno positivo dessa API confirma inserção no fluxo de entrada do Windows, sem comprovar consumo pelo aplicativo.

O usuário confirmou que a leitura funciona no VRPDV localmente e pelo AnyDesk instalado, mas falha pelo SmartPDV. Essa falha permanece em investigação. Os testes automatizados cobrem o transporte, as autorizações, a ordem dos dígitos e os eventos nativos Windows; não incluem o leitor físico nem o VRPDV.

Atualização: Central/Agent Windows 10/11 x64 1.0.5 e Agent Windows 7 SP1/.NET 4.8 0.1.4. Encerre os aplicativos antes de atualizar e use a mesma conta Windows para preservar o pareamento existente.
