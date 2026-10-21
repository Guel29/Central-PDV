# Cartão fiscal: análise e diagnóstico sem registrar o cartão

Status: a causa específica ainda não foi comprovada. Esta ferramenta **não é uma correção da leitura**. A VR deve continuar exigindo o cartão e validando-o normalmente. Nenhuma senha digitável, autorização automática ou alteração da VR é necessária para estes testes.

## Análise anterior à implementação

1. **Causa provável:** diferença no tratamento de leitores na tela fiscal, que pode depender da cadência, de prefixos/sufixos ou da origem do dispositivo. Os testes informados agora confirmam EAN remoto funcionando, cartão local aceito e cartão remoto recusado. Isso reduz a probabilidade de um bloqueio geral de teclado. Não demonstra sozinho Raw Input ou exigência de hardware físico.
2. **Mecanismo identificado no Smart Control:** Central Python 3.12/aiohttp, interface HTML/JavaScript e WebSocket TLS na LAN. `smartpdv/web/app.js` captura `keydown/keyup` quando a imagem tem foco e envia `key` e `code`. Não captura relatórios USB, identificador HID, prefixos fora dos eventos do navegador ou timestamps do leitor. Agent moderno Python e Agent Win7 C#/.NET 4.8 convertem as teclas para scan codes e chamam `SendInput`. Ambos impõem pressão mínima de 20 ms; não preservam a cadência original. Não existe dispositivo USB virtual no PDV. A versão **0.1.6 informada pelo usuário é do Agent**, não da VR.
3. **Mecanismo da VR:** desconhecido. Raw Input, HID direto, serial virtual, hook de teclado e classificação por velocidade permanecem hipóteses. A ferramenta não inspeciona o processo da VR, não injeta DLL e não identifica a API interna que ela usa. A confirmação depende dos resultados e, se necessário, da documentação/suporte da VR para a versão instalada.
4. **Solução recomendada:** comparar primeiro a leitura aceita e a recusada. Se houver perda de terminador/eventos ou divergência de cadência associada à regra documentada da VR, corrigir o transporte com base nessa evidência e validar no caixa. Se houver exigência de dispositivo, avaliar redirecionamento USB/HID oficialmente suportado pela VR e pelo fabricante da solução. Não instalar um driver virtual especulativo nem tentar esconder a origem sintética do evento.
5. **Arquivos alterados nesta etapa:** `diagnostics/Summary.cs`, `NativeCapture.cs`, `Program.cs`, projeto .NET, manifesto/configuração, testes, workflow Windows separado e documentação. **Central, Agents, protocolo de controle, política de permissões, F11, alarmes, cards e método de teclado permanecem iguais.**

## Diferenças relevantes

| Caminho | O que o Smart Control preserva/observa | O que não está comprovado |
|---|---|---|
| Digitação comum | Teclas físicas DOM e pressão/soltura via `SendInput` | Aceitação pela tela fiscal |
| EAN remoto | Mesmo caminho de teclado; funciona conforme o usuário | Que a tela fiscal use o mesmo tratamento da venda |
| Cartão fiscal remoto | Mesmo caminho de teclado; não é interpretado nem validado pela Central | Prefixos exatos, cadência exigida e API da VR |
| USB em modo teclado | Windows pode expor teclado HID e Raw Input por dispositivo | Que `SendInput` reproduza o dispositivo |
| Entrada simulada | Hook pode observar `LLKHF_INJECTED` | Que a VR rejeite precisamente essa marca |
| HID direto / serial | Inventário conta dispositivos HID e portas COM | Qual dispositivo ou porta a VR abre; a ferramenta não lê essas interfaces |

A documentação Microsoft distingue eventos de janela e Raw Input, que pode distinguir a origem por dispositivo. `SendInput` sintetiza entrada e tem limites de integridade/UIPI; retornar sucesso não confirma consumo pela VR. Executar o Agent como administrador já foi testado pelo usuário sem resolver, portanto não é apresentado como solução.

Fontes oficiais consultadas nos repositórios MicrosoftDocs:

- [Raw Input](https://github.com/MicrosoftDocs/win32/blob/docs/desktop-src/inputdev/about-raw-input.md)
- [SendInput](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/winuser/nf-winuser-sendinput.md)
- [Indicadores de injeção em KBDLLHOOKSTRUCT](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/winuser/ns-winuser-kbdllhookstruct.md)

## O que o diagnóstico faz

Executável portátil .NET Framework 4.8 x86. Projetado para Windows 7 SP1/.NET 4.8 e Windows 10/11 com .NET 4.8; a execução nativa automatizada é no Windows atual do CI, não em um caixa Windows 7 ou em hardware LS2208 real. Extraia o ZIP inteiro; mantenha o `.exe.config` junto do `.exe`. Não requer Python nem internet para executar. Não substitua o Agent por este executável.

Ao abrir, não instala observadores. **Preparar coleta** dá cinco segundos para voltar ao aplicativo; depois observa por até 30 segundos ou 10.000 eventos. **Parar**, fechar a janela e o término automático removem os observadores. O início depende de ação explícita e não existe autostart.

Escolha um dos dois observadores: **Teclado — indicadores e tempo** usa um hook `WH_KEYBOARD_LL` que sempre passa os eventos adiante; **Raw Input — origem do dispositivo** usa `RegisterRawInputDevices` para teclado com `RIDEV_INPUTSINK`, sem `NOLEGACY`, exclusividade ou bloqueio. Faça coletas separadas para cada observador e compare apenas arquivos do mesmo modo. A validação conjunta inicial não observou o canal de hook no CI; por isso não usamos uma coleta conjunta como diagnóstico válido. Isso é uma limitação da instrumentação, não evidência sobre a VR. A inscrição é no processo separado da ferramenta; ela não altera a inscrição Raw Input da VR. A coleta ocorre na sessão/desktop Windows interativa atual; não observa desktop seguro/UAC nem todas as sessões do computador.

Retém somente:

- Quantidade de eventos por categoria: dígito, dígito numérico, letra, Enter, Tab, modificador, função, navegação e outros. O primeiro e o último evento de pressão guardam somente a categoria, nunca o valor.
- Contagens de eventos marcados como injetados, sem marca de injeção, flags de extensão e scan code presente/ausente. Ausência da marca de injeção não prova hardware físico.
- Quantidade de mudanças da janela em foco, sem nome/título/PID da janela.
- Histograma dos intervalos entre pressões observadas pelos callbacks: abaixo de 5, 5–19, 20–49, 50–99 ou pelo menos 100 ms. Não é uma medição de barramento USB e pode sofrer atrasos de agendamento.
- Fontes Raw Input rotuladas `raw_keyboard_1` a `raw_keyboard_16` apenas durante a coleta; rótulos não identificam o mesmo aparelho em outra coleta. `raw_keyboard_no_device` significa que o Windows não informou um handle, sem presumir um dispositivo virtual.
- Quantidade de teclados/HIDs Raw Input e portas COM disponíveis. `-1` significa inventário indisponível. Não abre portas COM nem dispositivos HID.

Não guarda texto, ordem dos dígitos, valores individuais de teclas/scan codes, hashes, credenciais, imagens, caminhos de dispositivos ou número de série. Não traduz teclas em texto, não acessa o clipboard, não lê memória da VR e não se comunica pela rede. Prefixos/sufixos podem aparecer como categorias de controle, mas a ferramenta não reconstrói o prefixo exato, a sequência de símbolos ou sua posição entre os dígitos.

O resumo fica na memória. **Salvar resumo** é opcional: cria um JSON com ACL para a conta Windows atual e SYSTEM, grava arquivo temporário e faz renomeação atômica; não sobrescreve arquivo existente. Se não conseguir aplicar a ACL, o salvamento falha. Use pasta local NTFS. **Comparar resumos** importa exatamente dois arquivos com esquema restrito de até 64 KiB, sem executar seu conteúdo. **Limpar** descarta o resumo da memória. Não há log automático da ferramenta. Compartilhe apenas esses resumos, nunca o cartão ou fotos do código.

## Procedimento com o cartão real

Execute em uma janela de manutenção supervisionada, com o mesmo cartão autorizado e a mesma configuração de leitor usados na operação. Mantenha a autorização exclusivamente por cartão. Não compartilhe o código. Não teste senhas durante a coleta. Antes de iniciar, entre na tela desejada e confirme que nenhum outro operador está digitando.

1. Na Central, confirme o Agent conectado **0.1.6** no PDV Win7. Abra um atendimento pelo fluxo existente. Não há atualização de teclado nesta ferramenta.
2. Abra `SmartPDV-Input-Diagnostic.exe` na mesma conta/sessão Windows do aplicativo a observar. No PDV, a ferramenta pode ser aberta pelo atendimento remoto autorizado. Ela fica visível e não se instala em segundo plano.
3. Selecione **PDV**, **Cartão — leitor local** e **Teclado — indicadores e tempo**. Clique **Preparar coleta**, volte à tela fiscal em cinco segundos, aguarde o início e passe uma única vez o cartão pelo leitor conectado ao PDV. Confirme se a VR autorizou. Não digite mais nada; aguarde o término automático e salve como um arquivo novo. O resultado da VR deve ser anotado separadamente, apenas como “aceito” ou “recusado”.
4. Repita com **Produto — leitor local** em uma operação de teste apropriada. Essa é a referência de venda; o diagnóstico não cria nem cancela vendas.
5. Para a comparação remota, prepare a coleta no PDV com **PDV / Cartão — leitura remota**. Prepare também na Central com **Central / Cartão — leitura remota**. Volte à imagem remota e à tela fiscal antes de passar o cartão; faça a leitura uma vez quando ambas as coletas estiverem ativas. Se a preparação demorar, pare e refaça; é necessário haver sobreposição dos dois períodos de 30 segundos.
6. O leitor usado nessa etapa fica na **Central**. Confirme que a imagem remota tem foco e que o campo correspondente da VR foi selecionado pelo mouse remoto. Aguarde o fim das coletas e salve os dois resumos. Não altere velocidade, modo USB, prefixo ou sufixo do LS2208 entre o teste aceito e o recusado.
7. Repita a etapa remota com **Produto — leitura remota**, usando um código de produto de teste permitido. Registre apenas se a VR recebeu a leitura normalmente.
8. Se necessário, faça uma coleta **Digitação de teste** usando exclusivamente um número fictício em um Bloco de Notas vazio, para verificar a instrumentação. Não substitua o teste fiscal por isso.
9. Use **Comparar resumos** para escolher primeiro o resumo do PDV com cartão local aceito e o resumo do PDV com cartão remoto recusado. Depois compare Central e PDV durante a mesma leitura remota. Os cenários e locais estão dentro dos JSONs; não confie apenas nos nomes dos arquivos.
10. Repita as coletas local/remota escolhendo **Raw Input — origem do dispositivo**. Os dois canais são observados em leituras separadas; não interprete a falta de um canal desativado como ausência de entrada. Feche e reabra a ferramenta entre os modos.
11. Compartilhe os resumos e os resultados “aceito/recusado”, a versão da VR e o modelo/modo de interface do leitor. Não envie número do cartão, hash, credenciais ou telas que os exibam.

Se `streams` estiver vazio, o observador falhar, houver várias leituras ou muita digitação alheia, repita a coleta; não conclua a causa. Se o sistema ficar lento, clique **Parar** ou feche a ferramenta. O Agent e o atendimento continuam pelo mecanismo anterior.

## Como decidir a correção depois dos resultados

- Eventos faltantes ou Enter/Tab divergentes entre Central e PDV: localizar a perda no navegador/transporte, reproduzir com dados fictícios e corrigir apenas esse caminho. Este relatório não verifica igualdade dos dígitos por projeto.
- Cadência local e remota diferentes: confirmar com a VR se existe limite temporal de reconhecimento do scanner. Os 20 ms atuais são um candidato verificável, não uma causa estabelecida. Não remover globalmente essa proteção por tentativa, pois ela já faz parte do controle que funciona.
- Raw Input com dispositivo na leitura local, apenas entrada injetada na remota: diferença de origem confirmada no observador, mas requisito da VR ainda depende de documentação/validação. Não falsificar marcas ou identidades de dispositivos.
- VR confirmar HID/Raw Input/serial específico: avaliar a solução oficialmente homologada, suporte explícito ao Windows 7 SP1/.NET 4.8 do caixa e aos demais Windows, drivers assinados, licença, criptografia/autenticação na LAN, uso exclusivo durante atendimento autorizado e reversão. Compartilhar o leitor pode tirá-lo temporariamente da Central; isso precisa ser testado. Não há driver USB/HID implantado neste projeto.

Não é possível afirmar “corrigido” até testar a solução selecionada com o cartão real nessa mesma tela e verificar que cartões não autorizados continuam recusados pela VR.

## Acesso e auditoria: limite atual

A Central 1.0.9 abre sem login individual, conforme solicitação anterior. Ela exige origem local, sessão web local, pareamento do Agent por token/certificado TLS e dono do atendimento para encaminhar entrada. DPAPI/ACL protegem os cadastros na conta Windows. Isso **não identifica individualmente um supervisor** nem substitui uma política de conta Windows exclusiva. A escolha entre autenticação própria e conta Windows exclusiva foi solicitada ao usuário; nenhum novo login foi imposto nesta etapa. A ferramenta passiva não concede acesso remoto nem autentica um supervisor.

Os logs existentes de atendimentos solicitados continuam com PDV, horário da solicitação, supervisor, horário do atendimento e resultado, sem dados secretos. A auditoria atual não cobre de forma completa todos os acessos manuais fora de chamados e identifica o responsável como “Central”. Para cumprir auditoria individual de todos os acessos, será preciso tratar a autenticação escolhida e esse registro em alteração específica. Não alegamos que a implementação atual já cumpre esse requisito.

## Compilar e verificar no Windows

Com ferramentas de build .NET Framework 4.8/MSBuild:

```powershell
msbuild diagnostics/SmartPDV-Input-Diagnostic.csproj /p:Configuration=Release
```

A saída é `diagnostics/bin/Release/SmartPDV-Input-Diagnostic.exe`. O workflow **Input diagnostics (passive)** compila x86, testa resumos sem dependência dos números, esquema de importação, limites de tamanho/eventos, ACL, exportação atômica, observação de eventos Windows realmente injetados, parada e abertura da janela sem coleta automática. Não acessa hardware nem a VR. Publica um ZIP portátil, binário, configuração e SHA-256 em uma pré-versão separada; os instaladores da Central e do Agent não são substituídos.

## Relatórios vazios e versão 0.1.1

O usuário enviou resumos 0.1.0 de `keyboard_hook/manual` e `raw_keyboard/card_remote`, ambos com 30 segundos e `streams: {}`. Eles não registraram eventos e não permitem comparar a leitura do cartão. Não comprovam falha no leitor, uso de HID pela VR ou que nenhuma tecla tenha sido digitada. Não foram incorporados números de cartão ou arquivos particulares ao código.

A ferramenta 0.1.1 mostra a quantidade de eventos durante a coleta e **SEM EVENTOS** quando encerra vazia. O novo bloco `capture_health` contém apenas estado e contagens: chamadas do hook, mensagens Raw Input, falhas de leitura Raw Input, atividade geral da sessão Windows, correspondência com o desktop de entrada, sessão interativa e classificação do token do próprio processo. `input_activity` inclui mouse e teclado; não informa qual tecla, não prova leitura de cartão e não identifica o processo da VR. `input_desktop` é uma comparação no início, sem exportar o nome da área de trabalho; `process_token_level` não compara o Agent com a VR e não autoriza operações. Os registros de inscrição/thread indicam estado interno, não garantem que o Windows tenha entregue todos os eventos.

Esses metadados permitem separar coleta sem atividade observável, ambiente de entrada inacessível, falha de leitura de mensagens e ausência de callbacks apesar de atividade da sessão. Não são uma correção da transmissão fiscal. Relatórios 0.1.0 continuam legíveis; os novos campos usam esquema restrito e não aceitam texto livre, nomes de usuários ou caminhos.

O CI também passa a abrir o **WinExe distribuído**, operar seus seletores e botão Preparar por automação de interface, esperar a preparação real, enviar somente dados fictícios a uma janela de teste externa e verificar o JSON resultante. Há teste do término automático e da parada manual. A injeção é exclusiva de `UiProbe.cs`, executável de teste separado; não é compilada no diagnóstico distribuído.

Para validar a versão nova, use primeiro **Digitação de teste**, na Central, com `123456` e Enter em um Bloco de Notas vazio do próprio computador. Não use cartão fiscal nem senha para verificar o coletor. Aguarde os cinco segundos de preparação e digite dentro dos 30 segundos ativos. Compartilhe o resumo mesmo se aparecer SEM EVENTOS: o bloco de saúde permitirá examinar a ausência de captura. A necessidade de mudar privilégios ou o mecanismo de captura ainda deve ser verificada, sem presumir que executar como administrador resolva a leitura fiscal.
