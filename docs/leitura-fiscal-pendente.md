# Leitura fiscal remota ainda não resolvida

O usuário informou que a leitura continuou falhando após testar a atualização
atual, entregue com Central 1.0.11. Essa versão acrescentou recuperação do JSON;
não implementou outro motor de entrada. A preservação de cadência introduzida
na Central 1.0.10 / Agent Win7 0.1.7 não resolveu o problema no teste relatado.
Não houve nesta etapa nova alteração de teclado, instalador ou teste com a VR.

## O que o relato estabelece

- Leitura remota de EAN funciona, mas cartão fiscal remoto continua falhando.
- Cartão físico no PDV autoriza normalmente. A VR continua configurada para cartão.
- Digitação/colar não autorizam nessa tela. O usuário relatou funcionamento com
  AnyDesk instalado; não foi realizada comparação técnica dos dois motores.
- O Smart Control usa `SendInput` por scan codes, com rajadas temporizadas para
  eventos qualificados. Ele não apresenta um dispositivo USB/HID ao PDV.
- Permissão de teclado e resultado positivo de `SendInput` não comprovam que a
  tela fiscal reconheceu um leitor. A função de recuperação do JSON não muda isso.

Esses fatos não provam bloqueio de permissão, uso de Raw Input, exigência de USB
físico ou descarte por marca de injeção. Não alterar esses mecanismos por hipótese
nem remover proteções para tentar contornar a validação fiscal.

## Informação técnica necessária da VR

Texto para encaminhamento pelo responsável ao suporte da VR (sem dados do cartão):

> No VRPDV, a tela “PASSE O CARTÃO FISCAL” aceita um leitor Symbol LS2208 ligado
> diretamente ao caixa Windows 7. Pelo nosso controle remoto, EAN de produtos
> funciona, mas cartão fiscal não. Digitar ou colar também não autoriza; queremos
> manter exclusivamente a validação normal por cartão. Nosso Agent usa SendInput
> por scan codes; preservar os intervalos da leitura não resolveu o teste.
> Qual mecanismo essa tela usa: mensagens de teclado, Raw Input/WM_INPUT,
> interface HID/POS, serial ou outro? Ela exige prefixos/sufixos, terminador,
> origem de dispositivo ou alguma cadência específica? Qual método de controle
> remoto é oficialmente compatível nessa tela, mantendo as permissões e o cartão?
> Precisamos de compatibilidade com Windows 7, operação na LAN e sem senha fiscal.

A versão exata do VRPDV ainda não foi identificada: o número 0.1.6 fornecido
anteriormente era do SmartPDV Agent. Não pedir número do cartão, senha, captura
de leitura ou imagem contendo credenciais. Nenhuma mensagem foi enviada à VR por
este agente; o texto acima é apenas um modelo para o responsável.

## Alternativa nativa encontrada, ainda sem implementação

A documentação oficial da Microsoft descreve `IRDPSRAPISharingSession` e
`IRDPSRAPIViewer` em `RdpEncom.dll`, com requisito mínimo Windows Vista, e informa
que o Viewer continua suportado em aplicativos desktop. Trata-se de Windows
Desktop Sharing, uma opção para avaliar um motor nativo de sessão compartilhada.
Isso não comprova disponibilidade na instalação específica dos computadores,
compatibilidade fiscal, geração de eventos físicos ou redirecionamento do LS2208.

Fontes verificadas em 21/10/2026:

- [SharingSession](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/rdpencomapi/nn-rdpencomapi-irdpsrapisharingsession.md)
- [SharingSession.Open](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/rdpencomapi/nf-rdpencomapi-irdpsrapisharingsession-open.md)
- [Viewer](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/rdpencomapi/nn-rdpencomapi-irdpsrapiviewer.md)
- [Viewer.Connect](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/rdpencomapi/nf-rdpencomapi-irdpsrapiviewer-connect.md)

Uma eventual implementação precisaria de visualizador Windows nativo: o ActiveX
não funciona no dashboard Chrome/Edge como um script de teclado. Também exigiria
controlar convite, associação ao dono do atendimento, transporte autenticado e
criptografado, encerramento e reconexão; o TLS do dashboard não protege por si só
um segundo transporte. A API só permite uma SharingSession por sessão Winlogon
e exige STA. Sua existência não equivale a uma integração pronta.

Não criar nem publicar outro instalador como correção fiscal baseada apenas
nessa possibilidade. Identificar o mecanismo da VR ou obter uma validação
controlada do motor é necessário antes de afirmar compatibilidade.

## Redirecionamento USB

Reconfirmado no README oficial de `cezanne/usbip-win` v0.1.0: as instruções de
Windows 7 usam certificado e modo de assinatura de teste e declaram que o projeto
não está pronto para produção. Não foi adotado. A pesquisa anterior das outras
opções permanece em [usb-reader-redirection.md](usb-reader-redirection.md).

Continuam obrigatórios Windows 7, software gratuito, equipamentos existentes,
LAN protegida e validação normal por cartão. Não foi confirmada uma solução USB
de produção que cumpra essas condições. Isso não é prova de inexistência de
qualquer solução; é o limite do que foi verificado e implementado neste projeto.
