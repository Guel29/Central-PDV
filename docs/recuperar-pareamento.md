# Apaguei o JSON de pareamento do PDV

A Central 1.0.11 inclui **Gerar novo pareamento de PDV** no Menu Iniciar.
É compatível com o Agent Win7 0.1.7 e com o Agent moderno existente; não é
necessário atualizar o Agent para usar esse arquivo.

O arquivo exportado contém uma credencial. A Central guarda apenas seu hash:
não consegue reconstruir o segredo anterior depois que o arquivo foi apagado.
Gerar novamente substitui somente a credencial do PDV escolhido; preserva número,
identificador, certificado, rede, preferências e cadastros dos demais PDVs.

1. Instale a Central 1.0.11 na mesma conta Windows da Central atual.
2. Feche a Central. No caixa escolhido, encerre o Agent pelo Gerenciador de
   Tarefas (`SmartPDV-Agent-Win7.exe` no Win7 ou `SmartPDV-Agent.exe` no moderno).
3. No computador Central, abra **Menu Iniciar → Smart PDV Central → Gerar novo
   pareamento de PDV**. Informe o número já cadastrado, por exemplo `111`.
4. A janela informa o caminho do novo arquivo. Por padrão, pressione **Win+R**
   e abra `%LOCALAPPDATA%\SmartPDV\central\pairing`; copie `pdv-111.json`
   diretamente para o PDV por mídia segura. Não envie o arquivo pelo chat.
5. No PDV, com o Agent fechado, abra `%LOCALAPPDATA%\SmartPDV\agent` e renomeie
   somente `agent.json` para `agent-anterior.json`. Preserve essa cópia para
   referência das preferências anteriores. Não renomeie nem exclua `central.json`.
6. Abra **Configurar PDV** no Win7 ou **Configuração inicial** do Agent moderno.
   Selecione o novo JSON, confira o IP da Central e confirme o número. A configuração
   inicial usa os padrões do pareamento; preserve eventuais ajustes personalizados
   do arquivo anterior, sem copiar sua credencial antiga sobre a nova.
7. Inicie a Central e o Agent. Confira o card online e teste F11. Apague as cópias
   do arquivo de transferência depois de concluir o pareamento.

A credencial anterior desse PDV deixa de ser aceita ao gerar o novo cadastro.
Não é necessário recadastrar os outros caixas. A operação exige a Central
fechada para evitar que uma instância continue aceitando a credencial antiga
em memória. O arquivo e o cadastro são escritos atomicamente de forma individual;
se a atualização do cadastro falhar, o cadastro anterior é mantido e a exportação
não ativada é removida. Uma interrupção entre as duas gravações pode deixar uma
exportação não ativada: nesse caso, gere novamente antes de transferir.

Se somente atualizou o aplicativo e o Agent continua configurado, não precisa
gerar outro JSON. Se o arquivo ainda existir na pasta de pareamento, pode usar
essa cópia, desde que corresponda ao cadastro atual.

## Verificação desta atualização

Passaram 74 testes no Linux (3 testes nativos Windows ignorados). O [build Windows](https://github.com/Guel29/Central-PDV/actions/runs/39690214375) passou nos testes nativos, de transporte, de instalação e do novo atalho. Os testes de recuperação verificam preservação dos outros cadastros, rejeição da credencial antiga, conexão TLS com a nova credencial, recusa com Central aberta e falha de gravação sem revogar o cadastro anterior. Os instaladores publicados foram baixados e seus SHA-256 conferidos.

[Baixar Central 1.0.11](https://github.com/Guel29/Central-PDV/releases/download/windows-test-19-1/SmartPDV-Central-Setup.exe).
