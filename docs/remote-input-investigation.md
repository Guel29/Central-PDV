# Investigacao da leitura no VRPDV

Evidencia do usuario: o mesmo Symbol LS2208 e a digitacao fisica funcionam no VRPDV localmente e por um AnyDesk instalado. Pelo Smart PDV, a entrada chega ao Bloco de Notas remoto, mas nao funciona no VRPDV. Logo, o transporte basico nao demonstra compatibilidade com o aplicativo de destino.

O Agent atual e um processo interativo `asInvoker`, iniciado na conta do caixa, sem servico privilegiado. Usa SendInput com scan codes e uma duracao minima por tecla. Um processo pode ter entrada recusada pelo Windows quando tenta controlar outro de nivel superior. Mesmo quando SendInput retorna sucesso, isso nao confirma que o VRPDV consumiu a entrada.

A versao 1.0.4 / Agent legado 0.1.3 permite consultar a versao realmente em execucao e comparar os niveis dos tokens do Agent e do processo que esta em foco. O diagnostico somente consulta APIs do Windows; nao eleva privilegios, nao coleta teclas/EAN, nao grava imagens e nao muda politica de seguranca. O resultado e enviado apenas ao dono da sessao remota.

O fato de AnyDesk estar instalado e relevante, mas nao prova qual API, servico ou metodo ele esta usando nessa maquina. As paginas oficiais de suporte de teclado/elevacao foram tentadas neste ambiente e recusadas pela politica de rede (HTTP 403). Nenhum codigo interno do AnyDesk foi consultado ou copiado; nenhuma equivalencia com ele e afirmada.

Referencias publicas para verificacao externa das regras Windows (consulta web indisponivel neste ambiente):

- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation
- https://learn.microsoft.com/en-us/windows/win32/api/sas/nf-sas-sendsas

A verificacao ainda pendente e no computador do cliente com VRPDV em foco. Se o Agent tiver nivel inferior, corrigir a execucao/instalacao com autorizacao administrativa Windows e testar novamente antes de adotar outro metodo de entrada. Se nao houver diferenca, o nivel de permissao nao explica a falha e e necessario observar o metodo aceito pelo aplicativo. Os testes CI nao substituem esse teste no VRPDV.
