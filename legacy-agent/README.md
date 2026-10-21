# Agent Windows 7

Agent nativo separado, C# / .NET Framework 4.8, x86 (Windows 7 SP1 de 32 ou 64 bits).
A Central continua sendo o aplicativo para Windows 10/11. Nao execute os dois Agents no mesmo computador.

## Verificar o computador

1. Pressione Windows + R, digite `winver`, Enter. Procure **Service Pack 1**.
2. O instalador verifica se o **.NET Framework 4.8** esta instalado e interrompe com uma mensagem se estiver ausente. Instale o componente oficial Microsoft antes de continuar; nao e baixado automaticamente.
3. Instale `SmartPDV-Agent-Win7-Setup.exe` no usuario Windows que opera o caixa.
4. Na Central, cadastre o numero do PDV e exporte o pareamento. No assistente do Agent, selecione esse JSON, informe a Central e confirme o numero. Nao ha login do aplicativo.
5. Remova as copias do pareamento depois de importar. A credencial local fica protegida por DPAPI do usuario e ACL Windows.
6. O Agent inicia sem janela apos entrar no Windows. F11 envia o chamado. O operador continua usando seu sistema normalmente. O processo e a entrada de inicializacao permanecem identificaveis no Windows.

TLS 1.2 com pin SHA-256, WebSocket RFC6455 gerenciado (sem websocket.dll do Windows 8), reconexao automatica e configuracao JSON atomica. Captura GDI da tela principal: miniatura a cada 2 segundos, atendimento ate 4 fps e 1280x720 JPEG em memoria. Mouse/teclado somente em atendimento autorizado pela Central. Nao controla tela segura UAC nem aplicativos de privilegio superior. Nao grava imagens ou teclas.

## Desenvolvimento

No Windows com ferramentas MSBuild e referencias .NET Framework 4.8:

```powershell
msbuild legacy-agent/SmartPDV-Agent-Win7.csproj /p:Configuration=Release
.\legacy-agent\bin\Release\SmartPDV-Agent-Win7.exe
```

A workflow `Windows 7 Agent` compila, testa o protocolo TLS/pareamento/chamado/sessao com a Central real, gera instalador Inno Setup 6.2.2 e testa o executavel instalado. O modo explicito `--network-probe` e usado somente nesses testes: nao captura tela nem aplica entrada fisica. **Esses testes rodam em Windows moderno e nao substituem a validacao em Windows 7 real.** Captura, F11, controle fisico, desempenho e atualizacoes TLS do Windows 7 precisam ser verificados no equipamento de destino.

### Atualizacao 0.1.1

O Agent usa `SendInput` com scan codes Windows para o teclado remoto, incluindo o sinalizador de teclas estendidas e liberacao correspondente das teclas ao encerrar. Isso melhora a compatibilidade de entrada sem instalar drivers nem mudar o protocolo da Central. O instalador preserva `agent.json`, numero do caixa e pareamento. Encerre o Agent antes de atualizar e inicie novamente depois. Um teste Windows observa os eventos reais por hook (somente no executavel de testes) para validar digitos EAN, Enter e teclas estendidas. O VRPDV e o leitor fisico LS2208 nao estao disponiveis no CI; o resultado no aplicativo deve ser confirmado no caixa. Essa entrada continua sendo sintetica, sem redirecionamento USB e sem contornar restricoes de privilegio do Windows.

### Atualizacao 0.1.2

Pressao minima de tecla de 20 ms, ajustavel no JSON com `keyboard_min_press_ms` entre 0 e 100. A Central 1.0.3 mostra se o Windows aceitou ou recusou a entrada, sem coletar o codigo EAN ou as teclas. A recusa nao encerra a conexao. Isso permite diferenciar bloqueio do Windows de entrada aceita sem resposta do aplicativo. Ainda e necessario testar o VRPDV real; nao foi homologado por estes testes.
