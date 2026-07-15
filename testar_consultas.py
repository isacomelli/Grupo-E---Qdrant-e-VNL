from pathlib import Path
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range, PointStruct
import numpy as np

def imprimir_resultados(titulo, resultados):
    print(f"\n--- {titulo} ---")
    if not resultados:
        print("Nenhum resultado encontrado.")
        return
    for item in resultados:
        payload = item.payload if hasattr(item, "payload") else item.payload
        score = getattr(item, "score", None)
        score_str = f" | score={score:.4f}" if score is not None else ""
        print(
            f"id={item.id} | {payload['player_name']} ({payload['team']}) "
            f"| {payload['position']} | idade={payload['age']} | "
            f"altura={payload['height_cm']}cm{score_str}"
        )


def q1_busca_similaridade_pura(jogador_id, limite=5):
    """Q1: jogadores com perfil estatistico mais similar a um jogador de referencia."""
    ponto_referencia = client.retrieve(collection_name=COLLECTION, ids=[jogador_id], with_vectors=True)[0]

    resultados = client.query_points(
        collection_name=COLLECTION,
        query=ponto_referencia.vector,
        limit=limite + 1,  # +1 porque o próprio jogador retorna com score 1
    ).points

    # remove o próprio jogador da lista de resultados
    resultados = [r for r in resultados if r.id != jogador_id][:limite]
    imprimir_resultados(f"Q1 - Similares a '{ponto_referencia.payload['player_name']}'", resultados)


def q2_substituto_por_posicao(jogador_id, idade_maxima, limite=5):
    """Q2: busca vetorial + filtro de payload (substituto mais jovem na mesma posição)."""
    ponto_referencia = client.retrieve(collection_name=COLLECTION, ids=[jogador_id], with_vectors=True)[0]
    posicao = ponto_referencia.payload["position"]

    resultados = client.query_points(
        collection_name=COLLECTION,
        query=ponto_referencia.vector,
        query_filter=Filter(
            must=[
                FieldCondition(key="position", match=MatchValue(value=posicao)),
                FieldCondition(key="age", range=Range(lte=idade_maxima)),
            ]
        ),
        limit=limite + 1,
    ).points

    resultados = [r for r in resultados if r.id != jogador_id][:limite]
    imprimir_resultados(
        f"Q2 - Substitutos para '{ponto_referencia.payload['player_name']}' "
        f"({posicao}, idade <= {idade_maxima})",
        resultados,
    )


def q3_elenco_por_selecao(sigla_time, limite=20):
    """Q3: filtro puro, lista o elenco completo de uma seleção."""
    resultados, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(must=[FieldCondition(key="team", match=MatchValue(value=sigla_time))]),
        limit=limite,
    )
    imprimir_resultados(f"Q3 - Elenco da seleção {sigla_time}", resultados)


def q4_perfil_ideal(vetor_ideal, limite=5):
    """Q4: busca vetorial pura com vetor de teste ('perfil ideal' definido pelo scout)."""
    resultados = client.query_points(
        collection_name=COLLECTION,
        query=vetor_ideal,
        limit=limite,
    ).points
    imprimir_resultados("Q4 - Jogadores mais proximos do perfil ideal definido", resultados)


def q5_observados_multi_filtro(altura_minima, nacionalidade, idade_maxima, limite=20):
    """Q5: filtro múltiplo (altura x nacionalidade x idade), sem componente vetorial."""
    resultados, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="height_cm", range=Range(gte=altura_minima)),
                FieldCondition(key="nationality", match=MatchValue(value=nacionalidade)),
                FieldCondition(key="age", range=Range(lte=idade_maxima)),
            ]
        ),
        limit=limite,
    )
    imprimir_resultados(
        f"Q5 - Observados (altura >= {altura_minima}cm, {nacionalidade}, idade <= {idade_maxima})",
        resultados,
    )


def q6_atualizar_estatisticas(jogador_id, novo_vetor, novo_payload_parcial):
    """Q6: upsert/update, atualiza estatisticas (vetor e payload) de um jogador existente.
    Obs: como é um script de teste, ele salva o estado original do jogador e restaura no final."""

    original = client.retrieve(
        collection_name=COLLECTION, ids=[jogador_id], with_vectors=True
    )[0]

    payload_mesclado = {**original.payload, **novo_payload_parcial}

    client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=jogador_id, vector=novo_vetor, payload=payload_mesclado)],
    )

    atualizado = client.retrieve(
        collection_name=COLLECTION, ids=[jogador_id], with_vectors=True
    )[0]

    # Nota: o Qdrant armazena o vetor normalizado por L2 quando a colecao usa
    # distancia de Cosseno, entao a comparacao e feita por similaridade
    # (cosseno ~ 1), e nao por igualdade exata de valores.
    a, b = np.array(atualizado.vector), np.array(novo_vetor)
    similaridade = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    print(f"\n--- Q6 - Atualizacao de '{original.payload['player_name']}' ---")
    print(f"Payload atualizado: {novo_payload_parcial}")
    print(f"Vetor atualizado com sucesso: {similaridade > 0.999}")

    # Restaura o estado original para nao corromper a base entre execucoes.
    client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=jogador_id, vector=original.vector, payload=original.payload)],
    )
    print("(estado original restaurado apos a demonstracao)")


def q7_lookup_por_id(jogador_id):
    """Q7: lookup direto, perfil completo de um jogador pelo id."""
    resultado = client.retrieve(
        collection_name=COLLECTION,
        ids=[jogador_id],
        with_vectors=True,
    )
    print(f"\n--- Q7 - Perfil completo do jogador id={jogador_id} ---")
    if not resultado:
        print("Jogador nao encontrado.")
        return
    ponto = resultado[0]
    print(f"Payload: {ponto.payload}")
    print(f"Vetor: {ponto.vector}")


def buscar_id_por_nome(nome):
    resultados, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(must=[FieldCondition(key="player_name", match=MatchValue(value=nome))]),
        limit=1,
    )
    if not resultados:
        raise ValueError(f"Jogador '{nome}' nao encontrado na base.")
    return resultados[0].id

def load_env_file():
    env_file = Path(".env")
    if not env_file.exists():
        return
    
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

def main():
    print("Teste de Consultas (Q1 a Q7)")

    # exemplo resolvido por nome (id e reatribuido a cada ingestão)
    jogador_exemplo = buscar_id_por_nome("Darlan")  # BRA, oposto

    q1_busca_similaridade_pura(jogador_id=jogador_exemplo, limite=5)

    q2_substituto_por_posicao(jogador_id=jogador_exemplo, idade_maxima=27, limite=5)

    q3_elenco_por_selecao(sigla_time="BRA")

    # vetor de teste 
    vetor_ideal = [0.95, 0.1, 0.6, 0.3, 0.0, 0.36, 0.04, 0.24, 0.12, 0.0]
    q4_perfil_ideal(vetor_ideal=vetor_ideal, limite=5)

    q5_observados_multi_filtro(altura_minima=200, nacionalidade="BRA", idade_maxima=25)

    q6_atualizar_estatisticas(
        jogador_id=jogador_exemplo,
        novo_vetor=[0.95, 0.1, 0.65, 0.3, 0.0, 0.38, 0.04, 0.26, 0.12, 0.0],
        novo_payload_parcial={"age": 33},
    )

    q7_lookup_por_id(jogador_id=jogador_exemplo)

    print("Testes concluídos!")


load_env_file()

# Configurações do QDRANT
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION = os.environ.get("QDRANT_COLLECTION", "jogadores_vnl_2025")

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

if __name__ == "__main__":
    main()