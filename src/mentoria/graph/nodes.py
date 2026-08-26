"""Nodes do fluxo LangGraph.

Cada node tem uma responsabilidade unica. Nodes que consultam o LLM
recebem o modelo por injecao (facilita testes com um modelo fake). Nodes
puramente deterministicos (validacao, montagem, relatorio) nao dependem
do modelo, mantendo clara a separacao entre decisoes do modelo e regras
da aplicacao (requisito 4.2).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from mentoria import prompts, security
from mentoria.graph.state import AgentState
from mentoria.llm import parse_json_block
from mentoria.schemas import ComprehensionQuestion, Flashcard, MentorReport, RequestType
from mentoria.tools.dictionary import DictionaryResult, lookup_word

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from mentoria.memory import StudentMemory

MAX_MESSAGE_LEN = 5000

DictionaryLookup = Callable[[str], "DictionaryResult | None"]


def _memory(memory: StudentMemory | None) -> StudentMemory:
    if memory is not None:
        return memory
    from mentoria.memory import get_default_memory

    return get_default_memory()


def _level(state: AgentState) -> str:
    level = state.get("level")
    return level.value if level is not None else "B1"


# --- Nodes deterministicos --------------------------------------------------


def validate_input(state: AgentState) -> dict:
    """Valida a entrada (regra deterministica). Bloqueia entradas invalidas."""
    message = (state.get("message") or "").strip()
    if not message:
        return {"blocked": True, "block_reason": "Mensagem vazia.", "errors": ["input:vazio"]}
    if len(message) > MAX_MESSAGE_LEN:
        return {
            "blocked": True,
            "block_reason": f"Mensagem excede {MAX_MESSAGE_LEN} caracteres.",
            "errors": ["input:muito_longo"],
        }
    return {"blocked": False}


def screen_input(state: AgentState) -> dict:
    """Screening adversarial (deterministico) da entrada do aluno.

    Detecta prompt injection / entrada nao confiavel e sinaliza. NAO segue
    instrucoes contidas no conteudo: a mensagem segue sendo tratada apenas
    como tema/texto pelos nodes seguintes. Registra o evento para auditoria.
    """
    flags = security.detect_injection(state.get("message", ""))
    if not flags:
        return {"injection_detected": False, "injection_flags": []}
    return {
        "injection_detected": True,
        "injection_flags": flags,
        "errors": [f"security:prompt_injection:{'|'.join(flags)}"],
    }


def load_memory(state: AgentState, memory: StudentMemory | None = None) -> dict:
    """Recupera o perfil do aluno (temas recentes e termos ja vistos).

    Anonimo (sem student_id) nao acessa a memoria -> nenhum efeito colateral.
    """
    student_id = state.get("student_id")
    if not student_id:
        return {"known_terms": [], "recent_themes": []}
    profile = _memory(memory).get_profile(student_id)
    return {
        "known_terms": profile["known_terms"],
        "recent_themes": profile["recent_themes"],
    }


def persist_memory(state: AgentState, memory: StudentMemory | None = None) -> dict:
    """Registra a sessao e os termos vistos no perfil do aluno."""
    student_id = state.get("student_id")
    if not student_id:
        return {}
    mem = _memory(memory)
    intent = state.get("intent", RequestType.UNKNOWN)
    mem.record_session(
        student_id=student_id,
        request_type=str(intent),
        theme=state.get("theme"),
        run_id=state.get("run_id"),
    )
    terms = [item["term"] for item in state.get("vocab", [])]
    if terms:
        mem.record_terms(student_id, terms)
    return {}


def enrich_definitions(state: AgentState, lookup: DictionaryLookup = lookup_word) -> dict:
    """Node paralelo B: enriquece termos com fonetica/classe gramatical.

    Usa a Free Dictionary API (tool). Cada termo e resolvido de forma
    resiliente: falha ou palavra nao encontrada resulta em campos nulos,
    sem derrubar o fluxo. Escreve em `definitions`, chave distinta do node
    paralelo A, evitando conflito de escrita.
    """
    terms = [v["term"] for v in state.get("vocab", [])]
    definitions: dict[str, dict] = {}
    errors: list[str] = []
    for term in terms:
        try:
            result = lookup(term)
        except Exception as exc:  # noqa: BLE001 - resiliencia: nunca derruba o fluxo
            result = None
            errors.append(f"dictionary:{term}:{type(exc).__name__}")
        if result is not None:
            definitions[term] = {
                "phonetics": result.phonetic,
                "part_of_speech": result.part_of_speech,
            }
        else:
            definitions[term] = {"phonetics": None, "part_of_speech": None}
    updates: dict = {"definitions": definitions}
    if errors:
        updates["errors"] = errors
    return updates


def assemble_flashcards(state: AgentState) -> dict:
    """Junta vocabulario + exemplos + definicoes em flashcards (deterministico)."""
    vocab = state.get("vocab", [])
    examples = state.get("examples", {})
    definitions = state.get("definitions", {})
    cards = [
        Flashcard(
            term=item["term"],
            translation=item.get("translation", ""),
            example=examples.get(item["term"], ""),
            phonetics=definitions.get(item["term"], {}).get("phonetics"),
            part_of_speech=definitions.get(item["term"], {}).get("part_of_speech"),
        )
        for item in vocab
    ]
    return {"flashcards": cards}


def build_report(state: AgentState) -> dict:
    """Monta a saida estruturada final (deterministico)."""
    intent = state.get("intent", RequestType.UNKNOWN)
    level = state.get("level")
    notes = list(state.get("errors", []))

    if state.get("injection_detected"):
        notes.append(
            "Entrada adversarial neutralizada: o conteudo foi tratado apenas como "
            "dado (tema/texto). Instrucoes embutidas foram ignoradas e nenhuma "
            "informacao sensivel e revelada."
        )

    if state.get("blocked"):
        report = MentorReport(
            request_type=RequestType.UNKNOWN,
            level=level,
            summary=f"Solicitacao bloqueada: {state.get('block_reason', 'entrada invalida')}",
            notes=notes,
        )
        return {"report": report}

    if intent == RequestType.FLASHCARDS:
        cards = state.get("flashcards", [])
        summary = f"{len(cards)} flashcards gerados sobre '{state.get('theme')}'."
    elif intent == RequestType.READING:
        questions = state.get("questions", [])
        summary = f"{len(questions)} perguntas de compreensao geradas."
    else:
        summary = "Nao foi possivel classificar a solicitacao. Envie um tema ou um texto em ingles."

    report = MentorReport(
        request_type=intent,
        level=level,
        theme=state.get("theme"),
        reading_text=state.get("reading_text"),
        flashcards=state.get("flashcards", []),
        questions=state.get("questions", []),
        summary=summary,
        notes=notes,
    )
    return {"report": report}


# --- Nodes que usam o LLM (decisoes do modelo) ------------------------------


def classify_intent(state: AgentState, model: BaseChatModel) -> dict:
    """Classifica a intencao do aluno (decisao do modelo)."""
    messages = [
        SystemMessage(content=prompts.CLASSIFIER_SYSTEM),
        HumanMessage(content=prompts.classifier_user(state["message"])),
    ]
    try:
        data = parse_json_block(model.invoke(messages).content)
        intent = RequestType(data.get("intent", "unknown"))
    except (ValueError, KeyError, TypeError) as exc:
        return {
            "intent": RequestType.UNKNOWN,
            "errors": [f"classify:parse_error:{type(exc).__name__}"],
        }

    updates: dict = {"intent": intent}
    if intent == RequestType.FLASHCARDS:
        updates["theme"] = (data.get("theme") or state["message"]).strip()
    elif intent == RequestType.READING:
        text = (data.get("reading_text") or "").strip()
        theme = (data.get("theme") or "").strip()
        # Se nao veio texto mas veio tema, usa a mensagem original como contexto
        updates["reading_text"] = text if text else (theme or state["message"]).strip()
    return updates


def generate_vocabulary(state: AgentState, model: BaseChatModel) -> dict:
    """Gera vocabulario para o tema (decisao do modelo)."""
    theme = state.get("theme") or state["message"]
    messages = [
        SystemMessage(content=prompts.VOCAB_SYSTEM),
        HumanMessage(content=prompts.vocab_user(theme, _level(state), state.get("known_terms"))),
    ]
    try:
        data = parse_json_block(model.invoke(messages).content)
        vocab = [
            {"term": str(v["term"]).strip(), "translation": str(v.get("translation", "")).strip()}
            for v in data.get("vocab", [])
            if v.get("term")
        ]
    except (ValueError, KeyError, TypeError) as exc:
        return {"vocab": [], "errors": [f"vocab:parse_error:{type(exc).__name__}"]}
    return {"vocab": vocab}


def generate_examples(state: AgentState, model: BaseChatModel) -> dict:
    """Node paralelo A: gera frases de exemplo por termo (decisao do modelo)."""
    terms = [v["term"] for v in state.get("vocab", [])]
    if not terms:
        return {"examples": {}}
    messages = [
        SystemMessage(content=prompts.EXAMPLES_SYSTEM),
        HumanMessage(content=prompts.examples_user(terms, _level(state))),
    ]
    try:
        data = parse_json_block(model.invoke(messages).content)
        examples = {str(k): str(v) for k, v in data.get("examples", {}).items()}
    except (ValueError, KeyError, TypeError) as exc:
        return {"examples": {}, "errors": [f"examples:parse_error:{type(exc).__name__}"]}
    return {"examples": examples}


def generate_questions(state: AgentState, model: BaseChatModel) -> dict:
    """Gera perguntas de compreensao a partir do texto (decisao do modelo)."""
    reading_text = state.get("reading_text") or state["message"]
    messages = [
        SystemMessage(content=prompts.QUESTIONS_SYSTEM),
        HumanMessage(content=prompts.questions_user(reading_text, _level(state))),
    ]
    try:
        data = parse_json_block(model.invoke(messages).content)
        questions = [
            ComprehensionQuestion(
                question=str(q["question"]),
                answer=str(q.get("answer", "")),
                explanation=q.get("explanation"),
            )
            for q in data.get("questions", [])
            if q.get("question")
        ]
    except (ValueError, KeyError, TypeError) as exc:
        return {"questions": [], "errors": [f"questions:parse_error:{type(exc).__name__}"]}
    return {"questions": questions}
