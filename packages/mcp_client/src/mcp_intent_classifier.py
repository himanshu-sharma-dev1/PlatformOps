
from sklearn.metrics.pairwise import cosine_similarity
from llama_index.embeddings.ollama import OllamaEmbedding

#from IOT_Server.iotserver.MCPClient.mcpSetting import mcpSettings
from MCPClient.mcpSetting import mcpSettings

# Ollama embedder
embedder = OllamaEmbedding(
    model_name="nomic-embed-text",
    base_url="http://172.236.115.95:11434"
)


intent_list=mcpSettings.intent_list


def validate_intent_list(intent_list):
    if not isinstance(intent_list, list):
        return False, "intent_list must be a list"

    if not intent_list:
        return False, "intent_list is empty"

    for intent in intent_list:
        if not isinstance(intent, dict):
            return False, "Each intent must be a dict"

        if "name" not in intent or "description" not in intent:
            return False, "Intent must contain name and description"

        if not isinstance(intent["name"], str):
            return False, "Intent name must be string"

        if not isinstance(intent["description"], str):
            return False, "Intent description must be string"

    return True, "Intent list valid"
def build_intent_embeddings(intent_list):
    intent_names = []
    intent_embeddings = []

    for intent in intent_list:
        intent_names.append(intent["name"])
        emb = embedder.get_text_embedding(intent["description"])
        intent_embeddings.append(emb)

    return intent_names, intent_embeddings


def classify_top_2_intents(user_query: str, INTENT_EMBEDDINGS, INTENT_NAMES) -> list[str]:
    query_embedding = embedder.get_text_embedding(user_query)

    scores = cosine_similarity(
        [query_embedding],
        INTENT_EMBEDDINGS
    )[0]

    scored_intents = list(zip(INTENT_NAMES, scores))
    scored_intents.sort(key=lambda x: x[1], reverse=True)

    return [scored_intents[0][0], scored_intents[1][0]]

async def get_top_2_intents(user_query: str):
    intent_list = mcpSettings.intent_list


    ok, msg = validate_intent_list(intent_list)
    if not ok:
        raise RuntimeError(f"Intent config error: {msg}")


    intent_names, intent_embeddings = build_intent_embeddings(intent_list)

    if len(intent_embeddings) < 2:
        raise RuntimeError("Need at least 2 intents to classify")


    return classify_top_2_intents(
        user_query,
        intent_embeddings,
        intent_names
    )
