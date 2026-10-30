# Tradução PT-BR — Project Zomboid B42.13.1

Pacote de tradução para **Project Zomboid Build 42.13.1**, em português brasileiro.
Esta branch distribui os arquivos de tradução e seus relatórios de auditoria.
Para usar a tradução, basta copiar os TXT: não é necessário instalar Python,
Ollama, Node.js ou executar o Aray Zomboid Translator.

## O que está incluído

- **19 arquivos TXT PTBR**, contendo 10.665 entradas aprovadas/exportadas no fluxo
  de geração e **65 correções adicionais de QA** aplicadas ao pacote.
- `media/lua/shared/Translate/PTBR/`: arquivos destinados ao jogo.
- `auditoria-lua/PTBR/`: representações Lua usadas para auditoria técnica.
- CSVs, manifestos e relatórios com histórico, correções, hashes e limitações.

**Este é um complemento ao idioma PTBR do jogo, não uma cópia de toda a pasta de
idioma. Preserve os arquivos originais que não estão incluídos no pacote.**
A integridade técnica foi verificada; a semântica de todas as entradas não foi
revisada individualmente, e o pacote não foi testado em execução dentro do jogo.
Os detalhes estão em [RELATORIO_QA.md](RELATORIO_QA.md).

## Baixar a tradução

1. Abra a [branch b42.13.1](https://github.com/llongaray/ArayZomboidTranslator/tree/b42.13.1).
2. Confirme que o seletor de branch mostra **b42.13.1**.
3. Clique em **Code → Download ZIP** e extraia o arquivo.
4. Na pasta extraída, localize `media/lua/shared/Translate/PTBR/`.

Também é possível baixar o [ZIP direto desta branch](https://github.com/llongaray/ArayZomboidTranslator/archive/refs/heads/b42.13.1.zip).

## Instalação no Windows

### 1. Fechar o jogo e localizar a instalação

Confirme que está usando a **Build 42.13.1** e feche o Project Zomboid.
Na Steam, abra **Propriedades → Arquivos instalados → Explorar** para localizar a
pasta do jogo. Em uma instalação padrão, ela costuma ser:

```text
C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid\
```

Em outra unidade ou instalação, use a pasta que contém a pasta `media` do jogo.
Por exemplo, nesta instalação:

```text
E:\Games\Project.Zomboid.v42.13.1\game\
```

### 2. Fazer backup

Copie a pasta de idioma original para um local seguro, fora da pasta do jogo:

```text
<PASTA_DO_JOGO>\media\lua\shared\Translate\PTBR\
```

Guarde essa cópia para poder desfazer a instalação.

### 3. Copiar os arquivos

Copie **os 19 TXT** da pasta extraída:

```text
media\lua\shared\Translate\PTBR\
```

para a pasta correspondente dentro da instalação:

```text
<PASTA_DO_JOGO>\media\lua\shared\Translate\PTBR\
```

Aceite substituir os arquivos com os mesmos nomes. **Não apague a pasta PTBR
original e não remova os outros arquivos dela**, incluindo `language.txt`.
A estrutura final deve ser, por exemplo:

```text
<PASTA_DO_JOGO>/
└── media/lua/shared/Translate/PTBR/
    ├── BodyParts_PTBR.txt
    ├── Farming_PTBR.txt
    ├── IG_UI_PTBR.txt
    ├── ItemName_PTBR.txt
    ├── ... demais TXT deste pacote
    └── ... demais arquivos originais preservados
```

Não copie `auditoria-lua/`, os relatórios JSON ou os CSVs para a pasta do idioma.
Os arquivos `.lua` de auditoria não substituem os `.txt` utilizados pelo jogo.
Este pacote é uma instalação por cópia de arquivos; não possui instalador ou
estrutura de mod para colocar na pasta `mods`.

### 4. Ativar o idioma

Abra o jogo, acesse **Options/Opções**, procure **Language/Idioma** e selecione
**Brazilian Portuguese / Português brasileiro (PTBR)**. Aplique a configuração e
reinicie o jogo para recarregar os textos.

## Conferir a instalação

- Confirme que os TXT foram copiados diretamente para o diretório PTBR correto,
  sem criar uma pasta extra `PTBR/PTBR` ou `entrega-traducao` dentro do jogo.
- Confira textos de itens, agricultura e partes do corpo durante o uso normal.
- Se um mod fornecer traduções para as mesmas chaves, ele pode alterar os textos
  exibidos; confira também sua configuração de mods ao investigar divergências.
- Atualizações/verificações de arquivos pela Steam podem restaurar arquivos
  originais. Antes de reaplicar o pacote, confira a versão instalada.

A compatibilidade deste pacote está limitada à **B42.13.1**. Outras builds podem
usar chaves ou formatos diferentes.

## Desinstalar ou restaurar

Feche o jogo e restaure os arquivos a partir do backup da pasta PTBR. Caso algum
TXT do pacote não existisse na instalação original, remova somente esse arquivo
adicionado, comparando com o backup. Mantenha o restante da pasta de idioma.

## Auditoria e procedência

| Arquivo/pasta | Finalidade |
| --- | --- |
| `RELATORIO_QA.md` | Correções e limites da revisão independente |
| `CORRECOES_QA.csv` e `qa-review.json` | Antes/depois das 65 correções adicionais |
| `auditoria-traducao.csv` | Histórico das entradas e autoria disponível |
| `delivery-manifest.json` | Entradas entregues e hashes SHA-256 dos 19 TXT |
| `export-diagnostics.json` e `export-verification.json` | Resultados da validação/exportação |
| `linguistic-audit.json` | Triagem e correções contextuais anteriores ao QA |
| `auditoria-lua/` | Representações técnicas para auditoria; não instalar no jogo |

Alguns relatórios preservam caminhos locais e números históricos da geração.
Eles documentam a origem do pacote e não precisam existir no seu computador.
As 65 correções posteriores de QA estão nos arquivos desta branch; o checkpoint
do programa gerador não faz parte desta distribuição.

O procedimento de sobrepor traduções no diretório `media/lua/shared/Translate`
é descrito também no [repositório oficial de traduções da The Indie Stone](https://github.com/TheIndieStone/ProjectZomboidTranslations#testing-translations-locally).
