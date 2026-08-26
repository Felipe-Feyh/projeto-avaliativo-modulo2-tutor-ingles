"""Acoes administrativas com limites de autonomia e aprovacao humana.

Resetar o perfil de um aluno e uma acao DESTRUTIVA e IRREVERSIVEL. Por
politica de autonomia (requisito 4.5), ela NUNCA e executada automaticamente
pelo agente: exige aprovacao humana explicita.

Implementacao com LangGraph `interrupt()` + checkpointer (human-in-the-loop):
o grafo pausa no ponto de confirmacao e so executa o reset quando retomado
com uma decisao de aprovacao. Sem aprovacao, a acao e cancelada.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

if TYPE_CHECKING:
    from mentoria.memory import StudentMemory


class ResetState(TypedDict, total=False):
    student_id: str
    approved: bool
    done: bool
    removed: int
    message: str


def build_reset_graph(memory: StudentMemory, checkpointer=None):
    """Grafo de reset de perfil com gate de aprovacao humana (interrupt)."""
    if checkpointer is None:
        checkpointer = MemorySaver()

    def confirm(state: ResetState) -> dict:
        decision = interrupt(
            {
                "action": "reset_profile",
                "student_id": state["student_id"],
                "warning": "Acao destrutiva e irreversivel: apaga o historico do aluno.",
                "requires": "aprovacao humana explicita",
            }
        )
        return {"approved": bool(decision)}

    def do_reset(state: ResetState) -> dict:
        removed = memory.reset_profile(state["student_id"])
        return {"done": True, "removed": removed, "message": "Perfil resetado (aprovado)."}

    def cancel(state: ResetState) -> dict:
        return {"done": False, "removed": 0, "message": "Reset cancelado: nao aprovado."}

    def route(state: ResetState) -> str:
        return "approved" if state.get("approved") else "denied"

    graph = StateGraph(ResetState)
    graph.add_node("confirm", confirm)
    graph.add_node("do_reset", do_reset)
    graph.add_node("cancel", cancel)
    graph.add_edge(START, "confirm")
    graph.add_conditional_edges("confirm", route, {"approved": "do_reset", "denied": "cancel"})
    graph.add_edge("do_reset", END)
    graph.add_edge("cancel", END)
    return graph.compile(checkpointer=checkpointer)
