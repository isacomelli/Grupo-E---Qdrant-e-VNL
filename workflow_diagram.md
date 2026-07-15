# Application Workflow Diagram — Motor de Scouting VNL 2025

```mermaid
flowchart TD
    Home([Tela inicial])

    subgraph ENTRADA [Entrada e navegacao]
      direction LR
      Q3["Elenco da selecao<br/><b>Q3</b> · filtro de payload"]:::payload
      Q5["Lista de observados<br/><b>Q5</b> · filtro multiplo"]:::payload
      Q4["Perfil ideal sintetico<br/><b>Q4</b> · vetorial pura"]:::vetorial
    end

    Q7["Perfil do jogador<br/><b>Q7</b> · lookup por id"]:::payload

    subgraph ACOES [Acoes a partir do perfil]
      direction LR
      Q1["Jogadores parecidos<br/><b>Q1</b> · vetorial pura"]:::vetorial
      Q2["Substituto por posicao/idade<br/><b>Q2</b> · vetor + filtro"]:::hibrido
      Q6["Atualizar estatisticas<br/><b>Q6</b> · upsert"]:::escrita
    end

    Home --> ENTRADA
    Home -->|busca por nome/id| Q7
    ENTRADA --> Q7
    Q7 --> ACOES

    %% =================== ESTILOS ===================
    classDef vetorial fill:#f8b7b7,stroke:#c0392b,stroke-width:2px,color:#111;
    classDef hibrido  fill:#ffe08a,stroke:#c8a415,stroke-width:2px,color:#111;
    classDef payload  fill:#bfe3bf,stroke:#3d8b3d,stroke-width:2px,color:#111;
    classDef escrita  fill:#bcd6f5,stroke:#2b6cb0,stroke-width:2px,color:#111;
```

> Os resultados de Q1 e Q2 reabrem um novo perfil (Q7) — o laço de navegacao
> foi omitido do desenho para manter a leitura limpa.

**Legenda**

| Cor | Tipo de acesso | Consultas |
|-----|----------------|-----------|
| 🔴 Vermelho | Busca **vetorial pura** (similaridade de cosseno, sem filtro) | Q1, Q4 |
| 🟡 Amarelo | **Híbrido**: busca vetorial **+** filtro de payload | Q2 |
| 🟢 Verde | **Sem componente vetorial**: filtro de payload ou lookup por id | Q3, Q5, Q7 |
| 🔵 Azul | **Escrita** (upsert/atualização do ponto) | Q6 |

> Particularidade Vetorial (Qdrant): Q1 e Q4 usam **similaridade vetorial pura**;
> Q2 combina vetor com filtro de payload; Q3, Q5 e Q7 são acessos **apenas por
> payload/id**, sem componente vetorial; Q6 é a operação de **escrita**.
