# Estado atual do USB no Windows 7

A Central 1.1.0 e o Agent Win7 0.2.0 agora contêm a integração de controle e
transporte binário USB/IP sobre TLS. Consulte [instalação, operação e limites](usb-reader-redirection.md)
e o [relatório do que foi efetivamente executado](usb-validation-report.md).

**O programa ainda não está liberado para uso nos caixas.** O controlador virtual
Windows 7 continua dependendo de um pacote legitimamente assinado, não disponível
nesta tarefa. Implementar o aplicativo não elimina esse requisito do kernel.
Nenhuma assinatura de teste foi instalada e nenhuma proteção foi desativada.

Fontes dos componentes avaliados:

| Projeto | Fonte/revisão consultada | Resultado |
|---|---|---|
| [usbipd-win](https://github.com/dorssel/usbipd-win) | `c0ed08678af0e45ceead607f57da361fa403aa1a`, README e fonte; GPL-3.0-only | Servidor reutilizado no backend da Central Windows 10/11. Serviço/driver devem ser instalados separadamente de release oficial assinada. |
| [usbip-win2](https://github.com/vadimgrn/usbip-win2) | `9ff1fe0c71979e5b26c69f5b8dd4b1eeef6b7578`, README e LICENSE; BSD-2-Clause | Requer Windows 10 x64 1903+ ou Windows 11 ARM64; não foi adotado no PDV Windows 7. |
| [usbip-win v0.1.0](https://github.com/cezanne/usbip-win/tree/v0.1.0) | `44063583a5c3e20ec459bddadc9aae37f73bda10`, README, fonte, licença GPLv3 de topo e cabeçalhos GPLv2-ou-posterior | Backend cliente aberto/gratuito usado pela integração. Suporte Windows 7 declarado; README usa assinatura de teste e diz que não está pronto para produção. Assinatura legítima de produção/revisão e validação física continuam pendentes. |

A interoperabilidade de framing USB/IP entre os componentes foi analisada na fonte,
mas não equivale a teste dos drivers Windows. O teste real de transporte nesta
tarefa usa uma ponta TCP controlada, sem driver ou scanner. Há código do aplicativo
implementado e compilado; não há pacote SYS/CAT compilado/assinado pelo trabalho.

As restrições Windows 7, gratuidade e equipamentos existentes foram preservadas.
Não houve compra, troca de regra fiscal ou substituição por senha. Compatibilidade
com a autorização VR permanece pendente de reconhecimento do LS2208 no destino e
de autorização real por leitura de cartão, depois de resolver a instalação do driver.
