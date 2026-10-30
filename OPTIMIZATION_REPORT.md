> Relatório histórico da otimização inicial. A política de revisão humana descrita
> abaixo foi substituída pelo analista automático; consulte ANALYST_WORKFLOW.md.

# Otimização e diagnóstico — 30/10/2026

## Estado preservado

A execução anterior foi cancelada pela API e concluiu sua exportação parcial.
Foram preservadas 9.613 aprovações e 215 pendências de revisão. Backup completo
em `workspace/optimization-backup/20261030-002742/`, incluindo checkpoint,
resultados, revisões, histórico e estado do servidor. Os arquivos do jogo não
foram alterados. Os bloqueios de exportação anteriores permanecem nos diagnósticos
do backup; uma exportação parcial não significa que todos os arquivos foram entregues.

## Implementado

- Correções que repetem uma candidata anterior terminam em RH sem gastar outra
  geração. Respostas aprovadas e falhas estruturais continuam seguindo suas regras.
- Oito exceções revisadas, vinculadas à chave e ao EN exato: nomes GigaMart e
  Greene's, e ocorrências específicas de Hospital e Hotel. Não há aprovação
  genérica de palavras iguais, nomes presumidos ou de uma fonte que mudou.
- Lotes de até quatro textos, mesmo arquivo, cada texto com até 160 caracteres,
  até 600 caracteres somados. Textos longos, multilinha e correções ficam isolados.
- Cada item do lote é restaurado e validado individualmente. Um item inválido
  não descarta os válidos nem obriga suas traduções a serem geradas novamente.
- Prefixos internos como `K1 -` são bloqueados tanto na resposta do cliente quanto
  na validação compartilhada. A inspeção real encontrou três aprovações indevidas
  desse formato; foram copiadas para o backup, retiradas do checkpoint e da lista
  de aprovações, e a exportação foi refeita. Nenhum prefixo foi simplesmente
  removido para transformar texto inglês em uma aprovação aparente.
- Pendências de RH são preservadas em `review-checkpoint-v1.json`, por hash de
  arquivo/chave/EN, com candidata, motivos e histórico. Relatórios antigos de RH
  são importados e revalidados. Mudança no EN invalida a associação antiga.
- Aprovações e pendências são salvas em pequenos intervalos e no encerramento.
- O painel permite escolher lotes de 1, 2 ou 4 e mostra todas as entradas de uma
  chamada, sem confundir número de textos com número de workers.

As pendências preservadas continuam disponíveis na revisão humana. Para pedir
uma nova tradução delas, use a instrução por arquivo/entrada nessa seção.

## Medições neste PC

Ryzen 7 5700X, aproximadamente 32 GB de RAM, Radeon RX 6600. A API do Ollama
informou o Gemma 3 4B Q4_K_M inteiramente em VRAM, aproximadamente 2,9 GB.
Não foram alterados drivers, variáveis globais do Ollama ou limites de hardware.

Piloto com oito frases curtas de interface, incluindo placeholder:

| Workers | Textos/chamada | Chamadas | Tempo | Aprovadas |
|---:|---:|---:|---:|---:|
| 1 | 1 | 8 | 12,23 s | 8/8 |
| 2 | 1 | 8 | 8,25 s | 8/8 |
| 4 | 1 | 8 | 8,22 s | 8/8 |
| 1 | 4 | 2 | 4,19 s | 8/8 |
| 2 | 4 | 2 | 3,72 s | 8/8 |
| 4 | 4 | 2 | 4,17 s | 8/8 |

Com quatro workers, o ganho do lote nessa amostra foi aproximadamente 1,97x.
É um piloto com modelo aquecido e prefixos repetidos; não é uma garantia de ganho
no conjunto completo, especialmente nomes próprios, casos ambíguos e textos longos.

Conferência adicional com 16 frases distintas e quatro lotes:

| Workers | Rodada 1 | Rodada 2 | Aprovações em cada rodada |
|---:|---:|---:|---:|
| 4 | 7,44 s | 7,84 s | 16/16 |
| 2 | 7,92 s | 7,86 s | 16/16 |

As rodadas foram intercaladas. Não houve diferença suficiente para recomendar
aumentar a concorrência. Mantidos os quatro workers já escolhidos pelo usuário.

Após reforçar o prompt e bloquear prefixos internos, a medição final das mesmas
oito frases, com quatro workers, foi **9,20 s** em chamadas individuais e **4,24 s**
em lotes de quatro (8/8 aprovações nos dois casos): aproximadamente **2,17x** no
piloto. Casos reais problemáticos também foram retestados: continuaram como RH
quando não houve tradução, em vez de serem aprovados por carregarem um prefixo.

## Verificação

- 101 testes Python passaram e o build TypeScript/Vite passou.
- Testes de regressão: interrupção por repetição; exceções vinculadas à fonte;
  limite/separação de lotes; erro parcial; correção só do item reprovado; memória
  de RH e invalidação por mudança do EN; filas e percentual em tempo real.
- Teste completo com Ollama real, API Flask, SSE, checkpoint e exportação isolada:
  oito entradas, sete aprovações, uma revisão preservada, placeholder intacto,
  arquivo exportado e fonte sem alterações. Primeira execução: 3,41 s; retomada:
  0,14 s, sem inferências adicionais. Uma pendência não foi aprovada por ser reutilizada.
- Dados brutos em `workspace/optimization-benchmark.json`,
  `workspace/optimization-benchmark-validation.json` e
  `workspace/optimization-system-test/verification.json`. Medição final em
  `workspace/optimization-final-benchmark.json`; regressão real de prefixos em
  `workspace/optimization-prefix-regression.json`.
- Não foi realizada inspeção visual automatizada nesta rodada; o controle do
  navegador estava indisponível. A integração foi verificada por HTTP/SSE.

## Próximas melhorias para analisar — não implementadas

1. **Contexto de tradução:** fornecer chave, arquivo e domínio ao modelo. Hoje o
   prompt leva principalmente IDs e textos. Palavras curtas e ambíguas precisam
   distinguir nome de local, objeto, animal e ação antes de traduzir.
2. **Glossário contextual revisado:** ampliar agricultura, espécies, nomes de
   estabelecimentos e cognatos com pares chave/EN confirmados. Evitar deduzir
   automaticamente que todo texto em maiúsculas ou toda chave `Key` é nome próprio.
3. **Reutilização entre entradas equivalentes:** compartilhar resultados para o
   mesmo texto e contexto; nunca somente por igualdade do EN, pois a tradução pode
   variar com o sentido. Validar cada chave e seus placeholders separadamente.
4. **Métricas de qualidade e inferência:** exibir tokens/s, tempo de fila e geração,
   taxa de aprovação nova, chamadas por aprovação e tempo economizado. O percentual
   de processadas inclui RH; avanço não significa que todas ficaram traduzidas.
5. **Versão da fonte em decisões humanas:** guardar fingerprint também em
   `manual-decisions.json` para impedir reaplicar uma decisão antiga a um EN que
   mudou. Atualmente essas decisões usam identidade de arquivo/chave.
6. **Persistência transacional e auditoria incremental:** avaliar SQLite e
   reauditar apenas arquivos alterados se as medições mostrarem I/O relevante.
   Não apareceu evidência de que isso seja o principal gargalo deste piloto.
7. **Outros modelos:** comparar aprovação humana e tempo na mesma amostra difícil
   antes de trocar o modelo. Ganho de tokens/s sozinho não compensa mais erros/RH.
