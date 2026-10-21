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

A escolha pendente é se a integração pode depender de um componente com licença comercial ou precisa ser totalmente gratuita. Não foi feita compra, download/instalação de driver nem desativação de proteções Windows.

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
