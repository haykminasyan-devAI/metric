"""
RAG Retriever (dense-only)
──────────────────────────
Uses Metric's Armenian embeddings model with ChromaDB vector search.

Usage:
    retriever = BankRetriever()
    chunks = retriever.retrieve("Ֆասթ բանկի ավանդների տոկոսադրույքը", k=5)
"""

import os
import re
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "bank_data"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "Metric-AI/armenian-text-embeddings-1")


class BankRetriever:
    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None

    def _load(self):
        if self._model is None:
            self._model = SentenceTransformer(MODEL_NAME)
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=CHROMA_DIR,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_collection(COLLECTION_NAME)

    @staticmethod
    def _norm(text: str) -> str:
        t = text.lower()
        t = re.sub(r"[^0-9a-z\u0561-\u0586]+", "", t)
        return t

    def _detect_bank(self, query: str) -> Optional[str]:
        q = query.lower()
        q_norm = self._norm(query)
        aliases = {
            "Ameriabank": [
                "\u0561\u0574\u0565\u0580\u056b\u0561", "\u0561\u0574\u0565\u0580\u056b\u0561\u0562\u0561\u0576\u056f",
                "ameria", "ameriabank", "america bank",
            ],
            "Amio Bank": [
                "\u0561\u0574\u056b\u0578", "\u0561\u0574\u056b\u0578\u0576", "\u0561\u0574\u056b\u0578\u0562\u0561\u0576\u056f", "\u0561\u0574\u056b\u0578\u0562\u0561\u0576\u056f\u0568",
                "\u0561\u0574\u0575\u0578", "\u0561\u0574\u0575\u0578\u0562\u0561\u0576\u056f",
                "\u0561\u0574\u0565\u0578", "\u0561\u0574\u0565\u0578\u0562\u0561\u0576\u056f",
                "amio", "amio bank", "amiobank",
            ],
            "Fast Bank": [
                "\u0586\u0561\u057d\u0569", "\u0586\u0561\u057d\u0569\u0562\u0561\u0576\u056f",
                "\u0586\u0561\u057d\u057f", "\u0586\u0561\u057d\u057f\u0562\u0561\u0576\u056f",
                "\u0586\u0561\u057d\u057f \u0583\u0561\u0576\u056f", "\u0586\u0561\u057d\u057f \u057a\u0561\u0576\u056f",
                "fast", "fast bank", "fastbank",
                "\u057a\u0561\u057d\u057f \u0562\u0561\u0576\u056f",
                # STT variants: "Phastbank", "Fastbonk", "Phasbank"
                "\u0583\u0561\u057d\u0569\u0562\u0561\u0576\u056f", "\u0583\u0561\u057d\u057f\u0562\u0561\u0576\u056f",
                "\u0586\u0561\u057d\u056f\u0562\u0561\u0576\u056f", "\u0583\u0561\u057d\u056f\u0562\u0561\u0576\u056f",
                "\u0583\u0561\u057d\u0569 \u0562\u0561\u0576\u056f", "\u0583\u0561\u057d\u057f \u0562\u0561\u0576\u056f",
                "\u0556\u0561\u057d\u0569 \u0532\u0578\u0576\u0564",
            ],
            "Armeconombank (AEB)": [
                "\u0561\u0580\u0574\u0567\u056f\u0578\u0576\u0578\u0574\u0562\u0561\u0576\u056f",
                "\u0561\u0565\u0562", "aeb", "armeconombank",
                "\u0561\u0580\u0574\u0567\u056f\u0578\u0576\u0578\u0574",
                # STT variants: "Հay Ekon Bank", "Hay Ekonom"
                "\u0570\u0561\u0575 \u0587\u056f\u0578\u0576\u0578\u0574",
                "\u0570\u0561\u0575\u0587\u056f\u0578\u0576\u0578\u0574",
                "\u0570\u0561\u0575\u056f\u0561\u056f\u0561\u0576 \u0587\u056f\u0578\u0576\u0578\u0574\u0561\u056f\u0561\u0576 \u0562\u0561\u0576\u056f",
                "\u0570\u0561\u0575 \u0565\u056f\u0578\u0576\u0578\u0574 \u0562\u0561\u0576\u056f",
                "\u0570\u0561\u0575\u0565\u056f\u0578\u0576\u0578\u0574\u0562\u0561\u0576\u056f",
                "\u0587\u056f\u0578\u0576\u0578\u0574\u0562\u0561\u0576\u056f",
                "hay ekonom", "hayekonombank", "ekonombank",
            ],
        }
        for bank, keys in aliases.items():
            for k in keys:
                if k in q or self._norm(k) in q_norm:
                    return bank
        return None

    def _detect_section(self, query: str) -> Optional[str]:
        q = query.lower()

        deposit_keys = ["\u0561\u057e\u0561\u0576\u0564", "\u056d\u0576\u0561\u0575\u0578\u0572", "\u0564\u0565\u057a\u0578\u0566\u056b\u057f"]
        branch_keys = ["\u0574\u0561\u057d\u0576\u0561\u0573\u0575\u0578\u0582\u0572", "\u0570\u0561\u057d\u0581\u0565", "\u0561\u0577\u056d\u0561\u057f\u0561\u0576\u0584\u0561\u0575\u056b\u0576 \u056a\u0561\u0574", "\u056a\u0561\u0574\u0565\u0580", "branch", "address"]
        credit_keys = ["\u057e\u0561\u0580\u056f", "\u0585\u057e\u0565\u0580\u0564\u0580\u0561\u0586\u057f", "\u057e\u0561\u0580\u056f\u0561\u0575\u056b\u0576 \u0563\u056b\u056e", "\u0570\u056b\u0583\u0578\u0569\u0565\u0584", "overdraft", "loan"]

        has_deposit = any(k in q for k in deposit_keys)
        has_branch = any(k in q for k in branch_keys)
        has_credit = any(k in q for k in credit_keys)

        # If query mixes multiple sections, don't restrict — retrieve broadly
        detected = sum([has_deposit, has_branch, has_credit])
        if detected > 1:
            return None

        if has_deposit:
            return "DEPOSITS & SAVINGS"
        if has_branch:
            return "BRANCH LOCATIONS"
        if has_credit:
            return "CREDITS & LOANS"
        return None

    def _detect_fields(self, query: str) -> list[str]:
        q = query.lower()
        fields: list[str] = []

        rate_keys = ["\u057f\u0578\u056f\u0578\u057d", "\u057f\u0578\u056f\u0578\u057d\u0561\u0564\u0580", "tokos", "rate", "\u057f\u0578\u0563\u0578\u057d", "\u0569\u0578\u056f\u0578\u057d"]
        amount_keys = ["\u0563\u0578\u0582\u0574\u0561\u0580", "\u0561\u057c\u0561\u057e\u0565\u056c\u0561\u0563\u0578\u0582\u0575\u0576", "amount", "sum", "\u0574\u0561\u0584\u057d\u056b\u0574\u0561\u056c"]
        term_keys = ["\u056a\u0561\u0574\u056f\u0565\u057f", "\u0577\u0561\u0574\u056f\u0565\u057f", "\u056a\u0561\u0576\u056f\u0565\u057f", "term", "duration"]

        if any(k in q for k in rate_keys):
            fields.append("rate")
        if any(k in q for k in amount_keys):
            fields.append("amount")
        if any(k in q for k in term_keys):
            fields.append("term")
        return fields

    def _extract_field_lines(
        self, docs: list[str], metas: list[dict],
        fields: list[str], expected_bank: Optional[str] = None, max_lines: int = 16,
    ) -> list[str]:
        extracted: list[str] = []
        seen: set[str] = set()

        for doc, meta in zip(docs, metas):
            bank = (meta or {}).get("bank", "Unknown")
            section = (meta or {}).get("section", "")
            if expected_bank and bank != expected_bank:
                continue

            for raw_line in doc.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                low = line.lower()

                keep = False
                if "rate" in fields and ("\u057f\u0578\u056f\u0578\u057d" in low or "%" in line):
                    keep = True
                if "amount" in fields and ("\u0563\u0578\u0582\u0574\u0561\u0580" in low or "\u0564\u0580\u0561\u0574" in low or "amd" in low or "\u0574\u056c\u0576" in low):
                    keep = True
                if "term" in fields and ("\u056a\u0561\u0574\u056f\u0565\u057f" in low or "\u0561\u0574\u056b\u057d" in low or "\u057f\u0561\u0580\u056b" in low):
                    keep = True

                if keep:
                    tagged = "[" + bank + " \u2014 " + section + "] " + line
                    if tagged not in seen:
                        extracted.append(tagged)
                        seen.add(tagged)
                        if len(extracted) >= max_lines:
                            return extracted
        return extracted

    def _dense_search(self, query: str, bank: Optional[str], section: Optional[str], n: int = 20) -> list[dict]:
        embedding = self._model.encode(query, normalize_embeddings=True).tolist()

        where = None
        if bank and section:
            where = {"$and": [{"bank": bank}, {"section": section}]}
        elif bank:
            where = {"bank": bank}
        elif section:
            where = {"section": section}

        try:
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n,
                include=["documents", "metadatas", "distances"],
                where=where,
            )
        except Exception:
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        out = []
        for doc_id, doc, meta, dist in zip(ids, docs, metas, distances):
            out.append({
                "id": doc_id,
                "text": doc,
                "bank": meta.get("bank", ""),
                "section": meta.get("section", ""),
                "dense_dist": float(dist),
            })
        return out

    def retrieve(self, query: str, k: int = 5) -> str:
        self._load()

        bank = self._detect_bank(query)
        section = self._detect_section(query)
        is_branch_query = section == "BRANCH LOCATIONS"
        requested_fields = self._detect_fields(query)

        # Use more results for broad queries (no section filter)
        effective_k = k if section else max(k, 7)

        dense_results = self._dense_search(query, bank, section, n=20)
        top = dense_results[:effective_k]
        docs = [r["text"] for r in top]
        metas = [{"bank": r["bank"], "section": r["section"]} for r in top]

        if not docs and (bank or section):
            dense_results = self._dense_search(query, None, None, n=20)
            top = dense_results[:effective_k]
            docs = [r["text"] for r in top]
            metas = [{"bank": r["bank"], "section": r["section"]} for r in top]

        chunks = []
        for doc, meta in zip(docs, metas):
            b = meta.get("bank", "Unknown")
            s = meta.get("section", "")
            chunks.append("[" + b + " \u2014 " + s + "]\n" + doc)

        if requested_fields and not is_branch_query:
            field_lines = self._extract_field_lines(docs, metas, requested_fields, expected_bank=bank)
            if not field_lines:
                return (
                    "[STRICT_FIELD_MODE]\n"
                    "requested_fields: " + ", ".join(requested_fields) + "\n"
                    "EXACT_FIELD_NOT_FOUND"
                )
            return (
                "[STRICT_FIELD_MODE]\n"
                "requested_fields: " + ", ".join(requested_fields) + "\n"
                + "\n".join(field_lines)
            )

        payload = "\n\n---\n\n".join(chunks)

        if is_branch_query:
            payload += (
                "\n\n[BRANCH_SAFETY_RULE]\n"
                "\u0544\u056b \u0570\u0561\u0575\u057f\u0561\u0580\u0561\u0580\u056b\u0580, \u0578\u0580 \u0574\u0561\u057d\u0576\u0561\u0573\u0575\u0578\u0582\u0572 \u00ab\u0579\u056f\u0561\u00bb, \u0565\u0569\u0565 \u0564\u0561 \u0562\u0561\u057c\u0561\u0581\u056b\u0578\u0580\u0565\u0576 \u0576\u0577\u057e\u0561\u056e \u0579\u0567\u0589 "
                "\u0535\u0569\u0565 \u057f\u057e\u0575\u0561\u056c \u0584\u0561\u0572\u0561\u0584\u0568 \u0579\u056b \u0570\u0561\u0575\u057f\u0576\u0561\u0562\u0565\u0580\u057e\u0565\u056c \u057e\u0565\u0580\u0587\u0578\u0582\u0574 \u0570\u0561\u057f\u057e\u0561\u056e\u0576\u0565\u0580\u0578\u0582\u0574, \u0571\u0587\u0561\u056f\u0565\u0580\u057a\u056b\u0580\u2009\u2014\u2009"
                "\u00ab\u0561\u0575\u0564 \u0584\u0561\u0572\u0561\u0584\u056b \u0574\u0561\u057d\u0576\u0561\u0573\u0575\u0578\u0582\u0572\u056b \u057e\u0565\u0580\u0561\u0562\u0565\u0580\u0575\u0561\u056c \u057f\u057e\u0575\u0561\u056c \u0579\u0565\u0574 \u0563\u057f\u0565\u056c \u0561\u057c\u056f\u0561 \u057f\u057e\u0575\u0561\u056c\u0576\u0565\u0580\u056b \u0574\u0565\u057b\u00bb\u0589"
            )

        return payload

    def is_index_built(self) -> bool:
        try:
            client = chromadb.PersistentClient(
                path=CHROMA_DIR,
                settings=Settings(anonymized_telemetry=False),
            )
            col = client.get_collection(COLLECTION_NAME)
            return col.count() > 0
        except Exception:
            return False
