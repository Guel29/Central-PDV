# Investigacao da leitura no VRPDV

Evidencia do usuario: o mesmo Symbol LS2208 e a digitacao fisica funcionam no VRPDV localmente e por um AnyDesk instalado. Pelo Smart PDV, a entrada chega ao Bloco de Notas remoto, mas nao funciona no VRPDV. Logo, o transporte basico nao demonstra compatibilidade com o aplicativo de destino.

O Agent atual e um processo interativo `asInvoker`, iniciado na conta do caixa, sem servico privilegiado. Usa SendInput com scan codes e uma duracao minima por tecla. Um processo pode ter entrada recusada pelo Windows quando tenta controlar outro de nivel superior. Mesmo quando SendInput retorna sucesso, isso nao confirma que o VRPDV consumiu a entrada.

A versao 1.0.4 / Agent legado 0.1.3 oferecia uma consulta aos niveis de integridade dos processos. A pedido do usuario, essa consulta foi removida na versao 1.0.5 / legado 0.1.4. Era apenas um diagnostico; nao era uma barreira que autorizava ou bloqueava comandos.

As autorizacoes de teclado e mouse ficam na Central. Elas controlam o envio dos comandos existentes. Nao sao redirecionamento USB nem comprovam correcao da leitura no VRPDV. Veja [peripherals.md](peripherals.md) para os limites implementados e o trabalho ainda necessario para compartilhar dispositivos USB reais.

O fato de AnyDesk estar instalado e relevante, mas nao prova qual API, servico ou metodo ele esta usando nessa maquina. As paginas oficiais de suporte de teclado/elevacao foram tentadas neste ambiente e recusadas pela politica de rede (HTTP 403). Nenhum codigo interno do AnyDesk foi consultado ou copiado; nenhuma equivalencia com ele e afirmada.

Referencias publicas para verificacao externa das regras Windows (consulta web indisponivel neste ambiente):

- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation
- https://learn.microsoft.com/en-us/windows/win32/api/sas/nf-sas-sendsas

A causa da rejeicao pelo VRPDV continua sem comprovacao. A consulta removida nao chegou a produzir um resultado informado pelo cliente. Os testes CI nao substituem o teste no VRPDV e com o leitor fisico; nenhuma equivalencia de entrada com o AnyDesk foi verificada.

Na revisao 1.0.6 / legado 0.1.5 foi encontrada uma perda verificavel de identidade: `key` sozinho faz `Digit1` e `Numpad1` chegarem iguais ao Agent. A Central passa a transportar `code`, e os dois Agents o convertem no scan code fisico correspondente. A leitura continua no mesmo mecanismo SendInput. Nao foi demonstrado que essa perda era a causa da rejeicao pelo VRPDV; a verificacao no caixa permanece pendente.

O usuario informou que a atualizacao 1.0.6 tambem nao resolveu a leitura e solicitou retirar o campo EAN. A Central 1.0.7 remove o campo, a autorizacao exclusiva e o comando separado de codigos. A revisao dos filtros encontrou Escape consumido pela interface: agora ele e enviado quando a imagem remota tem foco. Nao foi encontrado filtro por nome de aplicativo ou por EAN no caminho de teclado dos Agents; a Central verifica autorizacao de teclado, formato e dono do atendimento. Isso nao comprova onde ocorre a rejeicao pelo VRPDV.

## Evidencia especifica: cartao fiscal na liberacao

O usuario mostrou a tela de atendimento com o rodape **PASSE O CARTAO FISCAL**. Confirmou que o leitor usado para a tentativa remota fica conectado na Central e que o mesmo cartao libera a operacao quando lido por um leitor diretamente no PDV. Portanto, o cartao e aceito pelo VRPDV nessa etapa; a falha observada depende do uso pela SmartCentral. A leitura de produtos funciona localmente. Ainda nao foi confirmado neste relato se produtos tambem sao lidos remotamente nessa mesma versao, nem se o AnyDesk foi comparado especificamente nesse prompt.

O usuario informou ter mantido a primeira versao no PDV; a versao exata do processo em execucao nao foi comprovada. A primeira implementacao net48 (`75089db`) usava `keybd_event(vk, 0, flags, ...)`, sem scan code explicito. As correcoes posteriores de scan code e identidade fisica exigem Agent atualizado; atualizar somente a Central nao altera o metodo nativo desse Agent antigo. Isso nao demonstra que um Agent posterior resolveria a liberacao.

O proximo teste de separacao e encerrar somente o Agent no PDV, iniciar o mesmo executavel com **Executar como administrador**, na mesma conta Windows do pareamento, e repetir a leitura pela Central nesse prompt. Trata-se de um teste de acesso do processo, com a confirmacao administrativa normal do Windows. Nao altera a autorizacao do cartao no VRPDV e nao e uma solucao permanente de inicializacao. Resultado posterior informado pelo usuario: o teste como administrador tambem nao liberou o cartao fiscal. Um resultado positivo sustentaria investigar o nivel de acesso na instalacao; um resultado negativo exige continuar a analise do metodo de entrada, sem declarar resolvido por permissao.

## Resultado da elevacao e identificacao do Agent

O usuario confirmou que executar como administrador nao resolveu e que o cartao fiscal contem **somente numeros**. Portanto, elevacao isolada nao foi uma solucao e perda de Shift/simbolos nao explica esse cartao. Nao ha evidencia suficiente para atribuir a causa a intervalo de teclas, Raw Input, foco ou origem fisica/sintetica; essas possibilidades nao sao tratadas como diagnostico confirmado.

A revisao encontrou uma dificuldade concreta de verificacao: no Agent legado, iniciar outra copia com o mutex da conta ja ocupado encerra silenciosamente. Isso permite instalar ou abrir outro executavel mantendo uma instancia anterior em execucao. O usuario mencionou ter mantido a primeira versao; a versao efetiva ainda nao foi identificada.

Central/Agent moderno 1.0.8 e Agent legado 0.1.6 incluem a versao informada pelo Agent no upgrade TLS autenticado. A Central mostra esse valor no card e no atendimento. Versoes anteriores aparecem sem versao informada. A identificacao e informativa, em memoria, sem alterar controle, privilegios, autenticacao ou metodo de teclado. Nao inclui conteudo digitado, cartao fiscal, senha, nome de aplicativo ou imagens. A Central limpa esses metadados ao desconectar e valida o formato informado. Isso nao e atestado criptografico do binario nem homologacao do VRPDV.

No Agent legado 0.1.6 a abertura manual informa se outra instancia ja esta rodando; a abertura automatica com --background continua silenciosa. Depois de atualizar, encerrar a instancia anterior e iniciar pelo atalho instalado, o card deve informar **0.1.6**. O proximo teste funcional deve usar essa versao confirmada na mesma tela PASSE O CARTAO FISCAL. Esta versao mantem o mecanismo anterior de entrada por scan codes; nao introduz outro metodo especulativo de teclado.

## Limpeza da interface 1.0.9

O usuario voltou a informar que a leitura desejada ainda nao funciona e pediu ocultar os comandos de autorizacao. A Central 1.0.9 remove o painel, as caixas de selecao e o botao de salvar; preserva a politica JSON existente e mostra um aviso caso teclado ou mouse estejam desativados nessa configuracao. Nao altera o mecanismo nativo de entrada. A revisao do caminho `keydown/keyup -> dashboard -> Agent -> SendInput` nao encontrou filtro por VRPDV ou por codigo fiscal. Isso nao identifica a causa da incompatibilidade.

O teste de navegador enfileira uma sequencia numerica ficticia com zeros iniciais e Enter antes de consumir os comandos do Agent de teste, verificando ordem e identidade das teclas. Esse Agent e simulado: o teste nao demonstra aceitacao pelo VRPDV. A versao efetivamente exibida no atendimento e a comparacao entre produto e cartao fiscal pela mesma conexao continuam necessarias para delimitar a falha sem pedir o conteudo do cartao.
