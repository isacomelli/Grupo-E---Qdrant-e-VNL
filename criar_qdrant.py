from pathlib import Path
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType


def create_collection(client, recreate=True):
    """Cria a coleção jogadores_vnl_2025 no Qdrant."""

    existe = client.collection_exists(COLLECTION)

    if existe and not recreate:
        return

    if existe and recreate:
        client.delete_collection(COLLECTION)

    print(f"Criando coleção '{COLLECTION}'")
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=DISTANCE),
    )

    for campo, tipo in PAYLOAD.items():
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=campo,
            field_schema=tipo,
        )

    info = client.get_collection(COLLECTION)
    print(f"Coleção: {COLLECTION}")
    print(f"Status: {info.status}")


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
    print("Criando banco de dados jogadores_vnl_2025.")

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=TIMEOUT)
    create_collection(client, recreate=True)

    print("Criação concluída!")


load_env_file()

# Configurações do QDRANT
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION = os.environ.get("QDRANT_COLLECTION", "jogadores_vnl_2025")

# embedding estatístico
VECTOR_SIZE = 10
DISTANCE = Distance.COSINE
TIMEOUT = 60

# Campos de payload
PAYLOAD = {
    "position": PayloadSchemaType.KEYWORD,
    "team": PayloadSchemaType.KEYWORD,
    "nationality": PayloadSchemaType.KEYWORD,
    "age": PayloadSchemaType.INTEGER,
    "height_cm": PayloadSchemaType.INTEGER,
}

if __name__ == "__main__":
    main()