# Preparação do driver Windows 7 — não é instalador

Estas ferramentas avançam a preparação da dependência USB/IP sem habilitar
TESTSIGNING, instalar certificado de teste, alterar firewall ou modificar o VR.
**Estes helpers tratam somente da dependência de driver; não geram um driver pronto para instalar.** A integração do aplicativo está descrita em [ponte USB](../../docs/usb-reader-redirection.md).

Foi reutilizada a fonte pública `cezanne/usbip-win v0.1.0`, commit
`44063583a5c3e20ec459bddadc9aae37f73bda10`, em vez de escrever outro controlador
virtual do zero. Consulte o [README oficial dessa revisão](https://github.com/cezanne/usbip-win/blob/v0.1.0/README.md).
O projeto não se declara pronto para produção. A licença de topo é GPLv3, com
arquivos individuais GPLv2-ou-posterior; os avisos permanecem na fonte exportada.
Não há autorização de distribuição de um binário novo implícita nesta preparação:
quando houver redistribuição, preservar os avisos e cumprir as licenças aplicáveis.

## Separação dos componentes

- `driver/vhci` da fonte externa: controlador virtual do PDV.
- `driver/stub` da fonte externa: captura USB do host Central, substitui driver
  de função do dispositivo selecionado; não instalar genericamente em HID/teclados.
- `userspace/src/usbip` e `usbipd`: utilitários/daemon externos. USB/IP bruto não
  fornece o transporte protegido e pareamento exigidos para esta solução.
- Aplicativo/serviços Smart Controle: ainda não integrados a esse backend. O
  aplicativo existente e o Agent Win7 não foram alterados para fingir conexão.

## 1. Preparar fonte verificável

Na raiz de `Central-PDV`, usando Python 3.12 e Git:

```powershell
py -3.12 tools/usb-win7/prepare.py --output build/usb-win7-source
```

O helper clona por HTTPS, exige o commit fixado e exporta a árvore do commit
usando `git archive`. Não copia arquivos locais/ignorados de um checkout nem suas
credenciais. Não sobrescreve destinos existentes; preserve-os e use outra pasta.
Com um checkout já disponível no commit exato:

```powershell
py -3.12 tools/usb-win7/prepare.py --source C:\fontes\usbip-win --output build/usb-win7-source
```

A saída inclui `smartpdv-source.json` com revisão e SHA-256 dos 127 arquivos de
fonte. Os hashes permitem detectar mudanças acidentais entre preparação e build;
não são assinatura de fornecedor e não substituem cadeia de confiança. A pasta
`build` é ignorada pelo Git; os drivers de terceiros não foram incorporados ao
código do aplicativo.

## 2. Build em computador Windows de desenvolvimento

Pré-requisitos externos, não instalados por estes scripts:

- Visual Studio 2019 com C++/MSVC v142 e MSBuild;
- Windows SDK e WDK 10.0.18362, conforme README do componente;
- Python 3.12/Git somente para preparar a fonte;
- Windows PowerShell 5.1 para os helpers de build/verificação (o **computador de
  build pode ser moderno**; isso não muda o requisito Windows 7 do caixa).

Exemplo no PowerShell, na raiz do projeto:

```powershell
.\tools\usb-win7\build.ps1 -Source .\build\usb-win7-source -Architecture x64 -MSBuild 'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe'
```

Para caixa 32 bits, usar `-Architecture x86`. O helper verifica os hashes e passa
`TargetVersion=Windows7` aos projetos, fixa SDK 10.0.18362, limita paralelismo a 2
e desativa a assinatura automática do build. Isso gera, se o build passar,
**artefatos não assinados**, nunca um pacote aprovado. Mantém um marcador
`NOT-FOR-INSTALLATION.txt`. Não confundir `Release` com assinatura de produção.
Não distribuir `Debug`, PFX de teste ou logs USB. Erros de toolchain devem ser
resolvidos sem desativar verificações do Windows.

Este build não foi executado neste ambiente Linux. A compatibilidade de todas as
propriedades com a instalação concreta do WDK ainda precisa ser validada. Não há
executáveis ou arquivos SYS/CAT compilados por esta entrega.

## 3. Assinatura e verificação antes de instalar

É necessário obter um pacote assinado para kernel com cadeia/política aceita pelo
Windows 7 de destino. Não há certificado/chave de produção disponível nesta tarefa.
O certificado de teste incluído no upstream **não resolve isso**. Não há promessa
de que um certificado comercial adquirido hoje forneça um caminho de assinatura
Windows 7, nem foi confirmada uma emissão gratuita. Validar o caminho com o
emissor/programa de assinatura antes de comprar ou submeter qualquer coisa.

Não foi automatizada a assinatura: o processo depende da identidade legítima do
responsável, do certificado/programa aceito e da infraestrutura de assinatura.
Nunca enviar chave privada/PFX ou senha no chat ou incluí-los no repositório.
Referência oficial: [requisitos de assinatura de drivers kernel](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/kernel-mode-code-signing-requirements--windows-vista-and-later-).

Quando houver um pacote legítimo assinado, o helper abaixo verifica arquivos
necessários e associação SYS/INF ao catálogo com a política kernel do SignTool,
considerando Windows 7 SP1:

```powershell
.\tools\usb-win7\verify-package.ps1 -Role PDV -Package C:\pacote-assinado\pdv -SignTool 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe'
```

Para o driver stub, usar `-Role Central`. O helper não assina, não instala, não
cria CAT e não declara homologação. Uma verificação no host de build não prova
carregamento em um Windows 7 com outra cadeia de confiança/atualizações. O conjunto
INF/CAT/SYS, arquitetura e confiança devem ser verificados no destino. O aplicativo
`usbip.exe` presente também exige origem/build auditados; verificar o catálogo do
driver não autentica automaticamente os executáveis de usuário.

**Não há comando de instalação liberado** enquanto essas etapas e revisão de
segurança do driver legado estiverem pendentes. Não abrir a porta USB/IP 3240 na
LAN: faltam túnel autenticado, autorização por dispositivo e serviços integrados.

## Estado verificado nesta tarefa

- Preparação real da fonte oficial fixada: executada; 127 arquivos exportados.
- Testes do helper: revisão errada recusada, destino preservado, hashes produzidos
  e travessia de diretórios em arquivo tar bloqueada.
- Build e verificação PowerShell/SignTool: não executados, ferramentas Windows
  ausentes neste executor Linux.
- Instalação, serviço, ponte pela LAN e reconhecimento LS2208/VR: pendentes.

Para remover apenas estes resultados, apagar a pasta de fonte/build escolhida.
Nenhum driver, certificado, serviço, regra de firewall ou tarefa foi instalado.
Os arquivos `tools/usb-win7` são ferramentas de desenvolvimento e podem ser
removidos sem afetar o Smart Controle em produção.
