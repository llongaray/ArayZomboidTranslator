# Revisão da lógica e distribuição de trabalho — 2026-10-29

Base analisada: commit c54de70. As recomendações abaixo ainda não foram implementadas;
a alteração desta revisão acrescenta somente o diagnóstico do Ollama e seus indicadores.

## Como funciona hoje

`Pipeline.run` audita, seleciona entradas, aplica CURATED e recupera traduções aprovadas
do checkpoint. `orchestrate_pipeline` distribui as restantes em uma fila compartilhada
por 1–4 threads tradutoras. Cada chamada leva uma entrada ao mesmo modelo Ollama.
Uma thread supervisora executa validações Python; uma thread gerente aplica regras
de aprovação ou devolve o item à fila, até três ciclos. Só os tradutores usam LLM.
Filas compartilhadas já permitem que um tradutor livre pegue a próxima entrada.

## Prioridades

1. **Garantir encerramento mesmo com falhas.** Em `staged_pipeline.py`, erros na
   criação do cliente, nos callbacks, na validação ou na decisão podem matar uma
   thread. O laço principal só verifica `left == 0`, sem conferir threads mortas.
   Proposta: validar configuração antes de iniciar, capturar erros por tarefa,
   garantir uma única conclusão por ID e propagar falhas fatais ao coordenador.
   Testar também erro de checkpoint, callback e cancelamento durante retry.

2. **Separar erro de infraestrutura de erro de tradução.** Hoje falha HTTP/timeout
   vira rejeição do supervisor e pedido de correção textual do gerente. Ollama
   parado pode consumir três tentativas por entrada e acabar como revisão humana.
   Proposta: estados tipados, checagem antes da primeira inferência, pausa global
   quando o serviço cai e tentativas com intervalo crescente. Preservar o trabalho
   pendente, sem classificar indisponibilidade como problema linguístico.

3. **Compartilhar o pré-processamento.** `translate_atom` no pipeline antigo trata
   fonte vazia, `likely_fixed` e `INVARIANT`; o pipeline ativo não repete essas
   decisões. CURATED já é aplicado em `jobs.py`. Extrair um único roteador para
   fonte inválida, tradução conhecida, invariável, PTBR existente e inferência.
   Evitar três caminhos divergentes: `cli.execute`, `agents.orchestrate` e o
   pipeline em estágios.

4. **Fazer o lote funcionar e limitar por tamanho.** `batch` é validado em
   `Pipeline.run`, mas não chega ao pipeline ativo: `batch_size=1` é fixo.
   Usar pequenos lotes de textos relacionados, limitados por orçamento de tokens.
   Texto longo deve seguir isolado; falha de um item deve resultar em retry desse
   item, sem repetir todos os aprovados. Ajustar os atuais limites fixos de 4096
   tokens de contexto e 768 de saída ao tamanho da requisição.

5. **Medir antes de aumentar workers.** As threads compartilham um servidor e um
   modelo; não são quatro modelos independentes. Registrar latência de fila,
   geração, tokens/segundo, erros, retries e entradas aprovadas/minuto. Comparar
   1, 2 e 4 workers com a mesma amostra. Separar concorrência de inferência da
   concorrência de validação. Não multiplicar supervisores/gerentes sem evidência
   de que são o gargalo.

6. **Corrigir o estado exibido.** Os slots de supervisor/gerente são atualizados,
   mas `complete` limpa o slot do tradutor. Podem permanecer como ativos entre
   tarefas; uma conclusão anterior também pode apagar o slot já reutilizado pelo
   tradutor. Emitir início/fim por etapa e ID de tarefa, com identidade separada do
   worker. Mostrar tradutores ocupados, filas e revisões separadamente.

7. **Evitar retries idênticos.** Com temperatura zero e contexto semelhante, a
   mesma saída pode reaparecer. Registrar hash das candidatas, interromper ciclos
   sem progresso e usar estratégias por motivo: placeholder, glossário, idioma,
   semântica. Os atuais validadores detectam padrões; aprovação não é garantia
   de equivalência semântica. Reservar revisão LLM adicional aos casos ambíguos.

8. **Reduzir I/O na finalização.** Cada aprovação regrava e sincroniza todo o
   checkpoint, dentro do callback executado sob o lock do pipeline. Para grandes
   volumes, considerar SQLite transacional ou um escritor dedicado com commits
   por intervalo/lote e flush obrigatório ao cancelar ou terminar. Persistir
   pendências, motivos e histórico, hoje gravado somente ao final.

## Distribuição proposta

Auditoria → pré-processamento determinístico → fila de inferência → validação
determinística → aprovação/exportação ou fila de correção → revisão humana.

O coordenador controla IDs, orçamento de tentativas e saúde do serviço. Tradutores
consomem pequenos lotes por arquivo/contexto; correções têm prioridade controlada
para não ficarem atrás de toda a fila inicial nem monopolizarem a execução.
Uma revisão semântica opcional recebe apenas casos de baixa confiança. Persistência
e interface recebem eventos, sem bloquear os consumidores de inferência.

## Diagnóstico Ollama acrescentado

- `GET /api/ollama/status?model=gemma3:4b&url=http://127.0.0.1:11434`.
- Consulta `/api/tags`, com timeout de socket de 2 segundos.
- Distingue API acessível/modelo instalado, modelo ausente, indisponibilidade,
  resposta inválida e configuração inválida; informa modelos e latência.
- Atualização automática nos painéis Flask e React, 10 segundos após cada consulta.
- Sem geração de tokens, download ou carregamento de modelos.
- A checagem não mede VRAM, fila interna, qualidade ou sucesso de inferência.
- A execução ainda não pausa nem bloqueia automaticamente em função desse estado.

## Validação

77 testes Python passaram; build TypeScript/Vite passou. Consulta real local
confirmou API acessível e `gemma3:4b` instalado. A venv existente aponta para um
Python 3.11 que não está mais nesse caminho; os testes usaram o Python fornecido
pelo aplicativo com as dependências existentes. Não foi feito benchmark de
inferência nem validação visual interativa dos painéis.
