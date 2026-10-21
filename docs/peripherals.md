# Periféricos autorizados pela SmartCentral

A autorização de entrada remota fica na Central, em `central.json`:

```json
"peripherals": {"keyboard": true, "mouse": true}
```

O painel **Autorizações de entrada — SmartCentral** controla o envio de comandos durante o atendimento pertencente à sessão da Central. A identificação dos computadores e o TLS permanecem necessários para a comunicação pela LAN.

## Controle direto

- Teclado: comandos enviados pela imagem remota, incluindo leitores USB em modo teclado, como o LS2208.
- Mouse: movimento, botões esquerdo/direito e rolagem na imagem remota.
- Revogação: comandos desativados são bloqueados pela Central; as teclas/botões já pressionados são liberados.
- Persistência: gravação atômica em JSON local. Se falhar, as opções anteriores continuam aplicadas. Sem banco de dados ou conteúdo digitado nos logs.

O navegador recebe teclas e não distingue um leitor em modo teclado de um teclado comum. A autorização não representa uma lista de dispositivos físicos e não altera permissões do Windows no PDV.

Na Central 1.0.7, o campo EAN, o botão de envio, o processamento separado de códigos e a autorização exclusiva de leitor foram removidos. O antigo comando `barcode` é rejeitado, inclusive quando o teclado está desativado. Em configurações anteriores, `scanner` é ignorado; salvar autorizações remove essa propriedade do JSON. O pareamento permanece.

Abra o atendimento e clique no campo do aplicativo dentro da imagem remota para controlar o PDV. Escape é encaminhado quando a imagem está em foco; **Encerrar atendimento** fecha a sessão. O navegador ainda pode usar Escape para sair da tela cheia.

## Teclas físicas e limites

A Central envia `KeyboardEvent.code` junto de `key`. Os Agents Windows 10/11 1.0.6 e legado 0.1.5 distinguem, por exemplo, `Digit1` de `Numpad1`, Enter numérico e lados dos modificadores. O botão **Windows no PDV** envia a tecla Windows ao remoto. Esta alteração do campo e de Escape é somente na Central; não exige reinstalar esses Agents.

Num Lock, Caps Lock e layout pertencem ao Windows de cada computador; seus estados não são sincronizados automaticamente. Atalhos reservados pelo sistema ou navegador podem não chegar à aplicação. Ctrl+Alt+Delete requer um mecanismo específico do Windows, ausente no controle atual; não é sintetizado por SendInput comum.

O controle utiliza entrada sintetizada por `SendInput`, sem criar um dispositivo USB no PDV. Redirecionamento USB genérico, enumeração por VID/PID e drivers virtuais não estão implementados.

## Falha no VRPDV: ainda sem correção comprovada

O usuário confirmou que LS2208 e teclado funcionam no Bloco de Notas remoto, mas não no VRPDV através do SmartPDV, inclusive após a versão 1.0.6. Localmente e pelo AnyDesk instalado, o leitor funciona. O Agent não consulta o nome do aplicativo para permitir ou negar entrada; ele chama SendInput na sessão interativa do Windows. A causa da diferença de comportamento ainda não foi determinada.

Os testes automatizados verificam transporte TLS, autorizações, identidade física das teclas, eventos nativos Windows, Escape, encerramento e persistência. Eles não substituem o teste com VRPDV/LS2208 real. A remoção do campo não é apresentada como solução dessa falha.

## Versão do Agent em execução (Central 1.0.8)

O card e o atendimento mostram a versão informada na conexão autenticada do Agent: 0.1.6 no legado Windows 7 ou 1.0.8 no moderno. Em Agents anteriores, aparece **Agent sem versão informada**. Esse aviso não bloqueia o controle. Versão e identificador do protocolo ficam apenas em memória e são apagados ao desconectar; não contêm códigos, credenciais ou teclas. A informação é declarada pelo próprio Agent e não certifica o binário. A instalação de outra versão não garante que uma instância anterior tenha encerrado; confirme a versão na Central após iniciar o atalho instalado.
