# Diagnóstico de entrada

Ferramenta passiva separada dos aplicativos operacionais. Consulte [a análise, os limites e o procedimento com cartão fiscal real](../docs/fiscal-card-diagnostic.md).

- .NET Framework 4.8, x86, início manual e coleta limitada a 30 segundos.
- Hook passivo e Raw Input de teclado; nenhum comando enviado e nenhum driver instalado.
- Somente categorias e contagens agregadas, sem dígitos, sequência ou hash do cartão.
- Nenhuma alteração no controle existente ou na autorização da VR.

`Tests.cs` é compilado somente no executável de testes do CI, nunca no programa distribuído. Os métodos de injeção nativa de testes não estão no executável de diagnóstico.
