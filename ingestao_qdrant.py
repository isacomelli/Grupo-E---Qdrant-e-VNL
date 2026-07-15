from pathlib import Path
import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import numpy as np
import pandas as pd

def min_max(serie):
    """Normalização min-max para o intervalo [0, 1]."""
    minimo, maximo = serie.min(), serie.max()
    if maximo > minimo:
        return (serie - minimo) / (maximo - minimo)
    return pd.Series(0.0, index=serie.index)


def taxa(sucessos, total):
    """Taxa de execução limpa = sucesso / total."""
    resultado = np.where(total > 0, sucessos / total.replace(0, np.nan), 0.0)
    return pd.Series(resultado, index=sucessos.index).fillna(0.0)


def taxa_escalar(sucessos, total):
    """Versao escalar de taxa para montar o payload por linha"""
    return sucessos / total if total > 0 else 0.0


def build_feature_matrix(df):
    """Calcula as 10 features (5 volume + 5 eficiência) do embedding."""
    features = pd.DataFrame(index=df.index)

    # Volume por partida (peso 1)
    features["ataque"] = min_max(df["Attacks Per Match"])
    features["bloqueio"] = min_max(df["Blocks Per Match"])
    features["saque"] = min_max(df["Serves Per Match"])
    features["backcourt"] = min_max(df["Digs Per Match"] + df["Receives Per Match"])
    features["levantamento"] = min_max(df["Sets Per Match"])

    # Eficiencia = sucesso / total de ações (peso PESO_EFICIENCIA)
    features["ef_ataque"] = min_max(taxa(df["Kills"], df["Kills"] + df["Attacking Errors"] + df["Attacking Attempts"])) * PESO_EFICIENCIA
    features["ef_bloqueio"] = min_max(taxa(df["Blocks"], df["Blocks"] + df["Blocking Errors"] + df["Rebounds"])) * PESO_EFICIENCIA
    features["ef_saque"] = min_max(taxa(df["Aces"], df["Aces"] + df["Service Errors"] + df["Service Attempts"])) * PESO_EFICIENCIA
    features["ef_recepcao"] = min_max(taxa(df["Successful Receives"], df["Service Receptions"])) * PESO_EFICIENCIA
    features["ef_levantamento"] = min_max(taxa(df["Running Sets"] + df["Still Sets"], df["Running Sets"] + df["Still Sets"] + df["Setting Errors"])) * PESO_EFICIENCIA

    return features


def parse_height(valor):
    return int(str(valor).replace("cm", "").strip())


def build_points(df, vetores):
    """Monta a estrutura dos pontos (id, vetor, payload) para upsert no Qdrant e retorna a lista de pontos.
    """
    total_acoes = df[COLUNAS_ACOES].sum(axis=1)

    pontos = []
    descartados = 0
    proximo_id = 0

    for idx, row in df.iterrows():
        if total_acoes.loc[idx] < MIN_ACOES:  # volume baixo demais = perfil nao confiável
            descartados += 1
            continue

        vetor = vetores.loc[idx].tolist()

        payload = {
            "player_name": row["Player Name"],
            "team": row["Team"],
            "nationality": row["Team"],
            "position": row["Position"],
            "age": int(row["Age"]),
            "height_cm": parse_height(row["Height"]),
            # métricas brutas mantidas no payload para exibição no Qdrant
            "stats_raw": {
                "attacks_per_match": float(row["Attacks Per Match"]),
                "kills": int(row["Kills"]),
                "attacking_attempts": int(row["Attacking Attempts"]),
                "blocks_per_match": float(row["Blocks Per Match"]),
                "serves_per_match": float(row["Serves Per Match"]),
                "aces": int(row["Aces"]),
                "digs_per_match": float(row["Digs Per Match"]),
                "receives_per_match": float(row["Receives Per Match"]),
                "sets_per_match": float(row["Sets Per Match"]),
            },
            # Taxas de eficiência (%)
            "efficiency": {
                "kill_pct": round(taxa_escalar(row["Kills"], row["Kills"] + row["Attacking Errors"] + row["Attacking Attempts"]) * 100, 1),
                "ace_pct": round(taxa_escalar(row["Aces"], row["Aces"] + row["Service Errors"] + row["Service Attempts"]) * 100, 1),
                "block_pct": round(taxa_escalar(row["Blocks"], row["Blocks"] + row["Blocking Errors"] + row["Rebounds"]) * 100, 1),
                "reception_pct": round(taxa_escalar(row["Successful Receives"], row["Service Receptions"]) * 100, 1),
                "setting_pct": round(taxa_escalar(
                    row["Running Sets"] + row["Still Sets"],
                    row["Running Sets"] + row["Still Sets"] + row["Setting Errors"],
                ) * 100, 1),
            },
        }

        pontos.append(
            PointStruct(
                id=proximo_id,
                vector=vetor,
                payload=payload,
            )
        )
        proximo_id += 1

    return pontos, descartados



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
    print("Ingestão de Dados no QDRANT")

    if not INPUT_CSV.exists():
        print(f"{INPUT_CSV} nao encontrado. Rode a partir da raiz do projeto.")
        return

    df = pd.read_csv(INPUT_CSV)

    vetores = build_feature_matrix(df)
    pontos, descartados = build_points(df, vetores)
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    if not client.collection_exists(COLLECTION):
        print(f"Coleção '{COLLECTION}' nao existe.")
        return

    lote = 100
    for i in range(0, len(pontos), lote):
        client.upsert(collection_name=COLLECTION, points=pontos[i:i + lote])

    info = client.get_collection(COLLECTION)
    print("Ingestão concluída!")
    print(f"Total de pontos: {info.points_count}")


load_env_file()

# Configurações do QDRANT
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION = os.environ.get("QDRANT_COLLECTION", "jogadores_vnl_2025")

DATA_DIR = Path("data")
INPUT_CSV = DATA_DIR / "playerStats.csv"

# Variáveis 
PESO_EFICIENCIA = 0.4
MIN_ACOES = 10

COLUNAS_ACOES = [
    "Kills", "Attacking Errors", "Attacking Attempts", "Aces", "Service Errors", "Service Attempts", "Blocks", "Blocking Errors", "Rebounds", "Successful Receives", "Receiving Errors", "Great Saves", "Defensive Errors", "Defensive Receptions", "Running Sets", "Still Sets", "Setting Errors",
]

if __name__ == "__main__":
    main()