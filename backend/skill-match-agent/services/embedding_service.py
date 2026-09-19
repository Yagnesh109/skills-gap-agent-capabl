import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger(__name__)

# Default threshold for declaring two skills semantically equivalent
# Values above 0.75 in all-MiniLM-L6-v2 indicate strong conceptual alignment (e.g. 'React' vs 'React.js UI library')
DEFAULT_SIMILARITY_THRESHOLD: float = 0.75


class EmbeddingService:
    """
    Singleton service for Sentence Transformers (all-MiniLM-L6-v2) embeddings and cosine similarity.
    Model is lazy-loaded on the first encoding request to preserve startup resources.
    """

    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold

    def _load_model(self):
        """Lazy load the SentenceTransformer model once."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer model '{self.model_name}'...")
                self._model = SentenceTransformer(self.model_name)
                logger.info("SentenceTransformer loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {e}")
                raise e
        return self._model

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Generates normalized embedding vectors for a single string or list of strings.
        Returns numpy array of shape (N, dim).
        """
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        model = self._load_model()
        # normalize_embeddings=True makes dot product equal to cosine similarity
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(embeddings, dtype=np.float32)

    def compute_similarity(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        """
        Calculates cosine similarity between two normalized embedding vectors.
        Returns float between -1.0 and 1.0 (typically 0.0 to 1.0 for normalized text).
        """
        if embedding_a.ndim == 1:
            embedding_a = embedding_a.reshape(1, -1)
        if embedding_b.ndim == 1:
            embedding_b = embedding_b.reshape(1, -1)

        sim = float(np.dot(embedding_a, embedding_b.T)[0][0])
        return max(0.0, min(1.0, sim))

    def compute_similarity_matrix(self, embeddings_a: np.ndarray, embeddings_b: np.ndarray) -> np.ndarray:
        """
        Calculates pairwise cosine similarity matrix between two sets of normalized embeddings.
        Shape: (len(embeddings_a), len(embeddings_b))
        """
        if embeddings_a.size == 0 or embeddings_b.size == 0:
            return np.zeros((len(embeddings_a), len(embeddings_b)), dtype=np.float32)
        matrix = np.dot(embeddings_a, embeddings_b.T)
        return np.clip(matrix, 0.0, 1.0)


# Global singleton helper instance
embedding_service = EmbeddingService()
