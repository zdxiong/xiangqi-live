"""TCHESS 接口返回的数据模型。"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MoveLine:
    """一条引擎推荐主线（PV）。"""
    pv: int = 0
    depth: int = 0
    score: int = 0
    mate: Optional[int] = None
    nps: int = 0
    time_ms: int = 0
    best_move: Optional[str] = None
    moves: List[str] = field(default_factory=list)
    move_cn: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["MoveLine"]:
        if not d:
            return None
        return cls(
            pv=d.get("pv") or 0,
            depth=d.get("depth") or 0,
            score=d.get("score") or 0,
            mate=d.get("mate"),
            nps=d.get("nps") or 0,
            time_ms=d.get("timeMs") or 0,
            best_move=d.get("bestMove"),
            moves=list(d.get("moves") or []),
            move_cn=d.get("moveCn"),
        )


@dataclass
class Analysis:
    """引擎分析结果：若干条主线 + 最佳主线。"""
    count: int = 0
    lines: List[MoveLine] = field(default_factory=list)
    best: Optional[MoveLine] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Analysis":
        if not d:
            return cls()
        return cls(
            count=d.get("count") or 0,
            lines=[MoveLine.from_dict(x) for x in (d.get("lines") or [])],
            best=MoveLine.from_dict(d.get("best")),
        )


@dataclass
class GameState:
    """当前局面与引擎状态。"""
    fen: str = ""
    red_to_move: bool = True
    side_to_move: str = "red"
    is_reverse: bool = False
    board: List[List[str]] = field(default_factory=list)
    engine_loaded: bool = False
    engine_name: str = ""
    move_diagnostics: str = ""
    analysis_mode: bool = False
    thinking: bool = False
    analysis: Analysis = field(default_factory=Analysis)

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        return cls(
            fen=d.get("fen", ""),
            red_to_move=bool(d.get("redToMove", True)),
            side_to_move=d.get("sideToMove", "red"),
            is_reverse=bool(d.get("isReverse", False)),
            board=[list(row) for row in (d.get("board") or [])],
            engine_loaded=bool(d.get("engineLoaded", False)),
            engine_name=d.get("engineName", ""),
            move_diagnostics=d.get("moveDiagnostics", ""),
            analysis_mode=bool(d.get("analysisMode", False)),
            thinking=bool(d.get("thinking", False)),
            analysis=Analysis.from_dict(d.get("analysis")),
        )
