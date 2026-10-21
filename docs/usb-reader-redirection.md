# Redirecionamento USB do leitor da Central

Status: levantamento técnico. **Ainda não há redirecionamento USB implementado ou driver selecionado no Smart Control.** O usuário interrompeu a investigação por relatórios e pediu disponibilizar diretamente o leitor USB da Central no PDV. A existência desta especificação não habilita USB no aplicativo.

## Operação pretendida

Leitor LS2208 conectado à Central → transporte USB pela LAN → driver cliente no PDV → leitura e validação normais da VR.

O computador onde está fisicamente conectado o leitor é o servidor USB; o PDV recebe o dispositivo pelo cliente USB. Capturar Raw Input na Central e enviar `SendInput` ao PDV continua sendo entrada de teclado sintetizada e não implementa esse caminho. A identificação do mecanismo exato da tela fiscal da VR continua desconhecida; redirecionamento deve ser validado nessa mesma tela antes de ser considerado compatível.

## Resultado do levantamento em fontes dos projetos

| Opção | Requisitos encontrados | Consequência para este projeto |
|---|---|---|
| [usbipd-win](https://github.com/dorssel/usbipd-win) | Host Windows 10/Server 2019 versão 1809 ou superior; documentação de conexão WSL e clientes USB/IP | Não fornece, sozinho, o cliente Windows 7 de que precisamos |
| [usbip-win2](https://github.com/vadimgrn/usbip-win2) | Windows 10 x64 versão 1903 ou superior / Windows 11 ARM64; drivers certificados/assinados nas distribuições apropriadas | A versão atual não atende ao PDV Windows 7 |
| [usbip-win](https://github.com/cezanne/usbip-win) | README informa que o último suporte Windows 7/8 é da versão v0.1.0; instruções usam certificados de teste e modo de assinatura de teste | Não adotar essas instruções de desenvolvimento como instalação de produção do caixa |
| Componente USB comercial integrado | Fornecedor, licença, SDK/CLI, versões Windows e assinaturas ainda precisam de confirmação | Alternativa em avaliação; nenhum fornecedor ou licença foi escolhido |

Fontes README consultadas em 21/10/2026. A disponibilidade de código ou de uma assinatura não comprova suporte ao LS2208/VR. Também será necessário confirmar autenticação e criptografia do transporte escolhido; não presumir que USB/IP básico as forneça.

A última resposta do usuário exige uma solução **totalmente gratuita**, substituindo a resposta anterior que aceitava componente licenciado. Não foi feita compra, download/instalação de driver nem desativação de proteções Windows. Não usar prazo de avaliação como comprovação de gratuidade permanente ou de licença para uso no supermercado.

A limitação pendente é o Windows do PDV: as alternativas gratuitas atuais confirmadas acima atendem Windows 10/11, enquanto o ramo antigo para Windows 7 documenta assinatura de teste. Ainda não foi confirmado um cliente gratuito com driver assinado para Windows 7. O usuário confirmou que **precisa manter o Windows 7**. Portanto, não oferecer a implementação limitada ao Windows 10/11 como cumprimento desse pedido. Windows 7 e gratuidade são restrições obrigatórias. A integração fica bloqueada pela falta de um driver gratuito assinado e compatível confirmado; não há recurso USB funcional entregue nesta etapa. A página oficial de termos do servidor VirtualHere foi tentada e recusada pela política de rede deste ambiente (HTTP 403); sua gratuidade e compatibilidade não foram confirmadas, e ele não foi selecionado.

Mesmo em Windows 10/11, será necessário implementar o transporte autenticado/criptografado e a concessão do leitor por atendimento. Encontrar um driver gratuito não significa que o recurso já esteja pronto no Smart Control.

## Integração exigida

1. Compartilhar somente o leitor explicitamente selecionado. Não compartilhar hub, todos os dispositivos USB ou o teclado/mouse do supervisor por seleção genérica.
2. O backend da Central só concede a sessão USB ao PDV cadastrado pertencente ao atendimento ativo do supervisor. O cliente não escolhe arbitrariamente outro servidor/dispositivo. O componente precisa permitir que a Central controle a associação, sem conexões permanentes por fora do atendimento.
3. Usar autenticação entre os computadores e criptografia na LAN. Cadastro/TLS da aplicação não protegem automaticamente um transporte USB paralelo. Portas, certificado e credenciais do componente devem ser configurados e protegidos explicitamente, sem serviço de nuvem.
4. Prever uso exclusivo do leitor: enquanto associado ao PDV, ele pode parar de produzir leituras locais na Central. O teclado e o mouse normais da Central continuam no caminho atual de controle.
5. Ao encerrar, alternar PDV, desconectar, perder o dono do atendimento ou expirar a concessão, liberar o dispositivo. Exigir do componente suporte a encerramento e recuperação; uma simples chamada de anexar USB sem reversão não é suficiente.
6. Não armazenar pacotes USB, conteúdo do cartão ou credenciais. Registrar somente metadados de acesso necessários e o resultado. A auditoria individual e a autenticação do supervisor ainda precisam ser alinhadas com a entrada direta atualmente configurada na Central.
7. Preservar o mecanismo de teclado/mouse que já funciona. Não usar esse mecanismo como fallback silencioso anunciando USB ativo. Se o dispositivo não foi anexado, a interface deve informar indisponibilidade.

## Critérios para selecionar o componente

- Driver de servidor para o Windows da Central e driver cliente para Windows 7 SP1 na arquitetura real do caixa; confirmar também os demais Windows atendidos.
- Assinatura confiável, requisitos de atualizações SHA-2 do Windows 7, procedimento de instalação/desinstalação e recuperação após reinício documentados pelo fornecedor.
- Suporte a leitores USB HID e ao modo em que o LS2208 está configurado, sem alterar silenciosamente essa configuração.
- Integração documentada por SDK/CLI, licença permitindo uso/distribuição, controle de associação por dispositivo e ausência de dependência de internet em operação.
- Transporte protegido e forma de restringir o acesso aos PDVs e atendimentos autorizados.
- Compatibilidade com a VR confirmada por teste ou orientação do fornecedor; não falsificar VID/PID ou a identidade de outro dispositivo para contornar validação.

## Arquivos previstos depois da seleção

O SDK/CLI e o modelo de segurança determinarão as alterações. Os pontos do projeto são `smartpdv/central.py` (dono/concessão do atendimento), `smartpdv/web/` (estado do leitor), integração Windows da Central e do Agent/`legacy-agent/`, e instaladores/rotinas de recuperação. O driver e seu componente local constituem uma dependência real; não substituí-los por um campo de EAN ou por simulação de teclas.

## Aceitação com o equipamento real

Validar o dispositivo anexado no PDV, leitura de produto e cartão fiscal válido na mesma tela, rejeição normal de cartão não autorizado pela VR, devolução à Central, alternância entre dois PDVs, encerramento forçado, queda da LAN, reinício da Central/Agent e restauração da configuração anterior. Fazer os testes em janela supervisionada sem capturar o número do cartão. Até esses testes, não afirmar correção fiscal nem equivalência com outros aplicativos de acesso remoto.

## Alternativas para entrada semelhante à local, mantendo cartão

O usuário reiterou que a autorização deve continuar exclusivamente por cartão e pediu outra forma de a leitura funcionar como local. Nenhuma mudança para senha foi feita no Smart Control nem na VR.

### Driver de entrada Interception

O [README oficial do Interception](https://github.com/oblitum/Interception/blob/master/README.md) informa testes entre Windows XP e Windows 10 e distingue uso não comercial de uso comercial. Para uso comercial, descreve licenças comerciais específicas. Portanto, a distribuição pública não foi selecionada como solução gratuita para o supermercado. Sua API é de interceptação/envio de entrada e não constitui, por si só, redirecionamento USB do LS2208. Nenhum driver foi instalado ou incorporado.

### Adaptador físico USB/HID por PDV

Uma alternativa técnica é um módulo com USB nativo, por exemplo ESP32-S3 com conector USB-OTG acessível, ligado fisicamente ao PDV. Ele recebe eventos autorizados pela LAN e produz relatórios de teclado USB HID. O Windows usa a pilha HID/teclado do próprio sistema. Isso fornece um novo dispositivo de teclado USB físico; não transporta a interface USB completa do LS2208 nem reproduz sua identidade de fabricante. A aceitação pela tela fiscal da VR continua dependendo de teste real, especialmente se ela exigir uma coleção HID específica, identidade do leitor ou protocolo serial.

O [exemplo oficial ESP-IDF TinyUSB HID](https://github.com/espressif/esp-idf/tree/master/examples/peripherals/usb/device/tusb_hid) demonstra dispositivo teclado/mouse USB em ESP32-S2/S3 e outros alvos com USB-OTG. A [arquitetura HID documentada pela Microsoft](https://github.com/MicrosoftDocs/windows-driver-docs/blob/staging/windows-driver-docs-pr/hid/hid-architecture.md) descreve a pilha de drivers fornecida pelo Windows e as coleções teclado/keypad. Essas fontes sustentam a arquitetura, não uma homologação de cartão fiscal VR.

O firmware pode ser desenvolvido sem licença comercial paga, mas o módulo e o cabo têm custo de compra. Foi solicitado ao usuário esclarecer se pode haver hardware adicional ou se a solução precisa usar somente os equipamentos existentes. Não houve compra nem recomendação de um modelo fechado sem confirmar conexão USB nativa e rede. Um ESP32 sem USB-OTG ou um conector ligado apenas a conversor serial não atende ao papel de dispositivo HID descrito aqui.

Fluxo proposto: leitor da Central → sessão autorizada no Smart Control → LAN autenticada/criptografada → módulo associado exclusivamente ao PDV atendido → relatórios USB HID → validação normal do cartão pela VR. A rede pode ser Wi-Fi na mesma LAN ou Ethernet com módulo apropriado; não presumir que exista Wi-Fi no caixa. É necessário preservar a cadência observável, os controles/prefixos/terminadores suportados e impedir duplicação entre o envio normal de teclado e esse caminho.

A integração deve limitar-se ao atendimento ativo, limpar estados de teclas ao encerrar/perder conexão, descartar dados pendentes ao reconectar e impedir reapresentação automática do cartão. As leituras ficam apenas em trânsito/memória, sem conteúdo ou hash nos logs. O módulo deve ter identidade de dispositivo própria, sem clonar VID/PID do LS2208. Não há protótipo de firmware ou integração funcional entregue nesta etapa.

### Alternativa somente por software: cadência

O código atual do Agent impõe 20 ms mínimos por tecla e não preserva os tempos originais do leitor. Reprodução de uma leitura agrupada com cadência preservada é uma hipótese para telas que distinguem scanner por velocidade; não transforma a entrada em USB físico. A versão inicial também foi relatada com falha, portanto os 20 ms não podem ser declarados causa única. Sem identificar a regra da tela da VR ou obter uma comparação válida no equipamento, essa alternativa não foi implementada como se fosse uma correção comprovada.

## Equipamentos atuais e tentativa de cadência

O usuário confirmou que a solução deve usar **somente os computadores e leitores atuais**, sem adaptadores. Mantém Windows 7 e gratuidade. A ponte física permanece excluída.

Foi identificada uma alteração artificial de cadência no teclado remoto; a tentativa de preservá-la está descrita em [teste-cadencia-leitor.md](teste-cadencia-leitor.md). Essa melhoria não implementa redirecionamento USB e não confirma o mecanismo de autorização fiscal da VR.
