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
