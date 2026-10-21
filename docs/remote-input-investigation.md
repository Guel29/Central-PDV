# Investigacao da leitura no VRPDV

Evidencia do usuario: o mesmo Symbol LS2208 e a digitacao fisica funcionam no VRPDV localmente e por um AnyDesk instalado. Pelo Smart PDV, a entrada chega ao Bloco de Notas remoto, mas nao funciona no VRPDV. Logo, o transporte basico nao demonstra compatibilidade com o aplicativo de destino.

O Agent atual e um processo interativo `asInvoker`, iniciado na conta do caixa, sem servico privilegiado. Usa SendInput com scan codes e uma duracao minima por tecla. Um processo pode ter entrada recusada pelo Windows quando tenta controlar outro de nivel superior. Mesmo quando SendInput retorna sucesso, isso nao confirma que o VRPDV consumiu a entrada.

A versao 1.0.4 / Agent legado 0.1.3 oferecia uma consulta aos niveis de integridade dos processos. A pedido do usuario, essa consulta foi removida na versao 1.0.5 / legado 0.1.4. Era apenas um diagnostico; nao era uma barreira que autorizava ou bloqueava comandos.

As autorizacoes de teclado, mouse e campo EAN agora ficam na Central. Elas controlam o envio dos comandos existentes. Nao sao redirecionamento USB nem comprovam correcao da leitura no VRPDV. Veja [peripherals.md](peripherals.md) para os limites implementados e o trabalho ainda necessario para compartilhar dispositivos USB reais.

O fato de AnyDesk estar instalado e relevante, mas nao prova qual API, servico ou metodo ele esta usando nessa maquina. As paginas oficiais de suporte de teclado/elevacao foram tentadas neste ambiente e recusadas pela politica de rede (HTTP 403). Nenhum codigo interno do AnyDesk foi consultado ou copiado; nenhuma equivalencia com ele e afirmada.

Referencias publicas para verificacao externa das regras Windows (consulta web indisponivel neste ambiente):

- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation
- https://learn.microsoft.com/en-us/windows/win32/api/sas/nf-sas-sendsas

A causa da rejeicao pelo VRPDV continua sem comprovacao. A consulta removida nao chegou a produzir um resultado informado pelo cliente. Os testes CI nao substituem o teste no VRPDV e com o leitor fisico; nenhuma equivalencia de entrada com o AnyDesk foi verificada.
