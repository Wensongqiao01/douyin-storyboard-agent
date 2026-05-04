"""文字模糊匹配工具

将 DeepSeek 引用的文字片段匹配回 Whisper 的字级时间戳。
"""

from typing import Optional

from rapidfuzz import fuzz

from models.schemas import WordTimestamp

# 模糊匹配默认阈值
_DEFAULT_SCORE_CUTOFF = 60.0
# 滑动窗口长度倍数上限
_WINDOW_LENGTH_MULTIPLIER = 1.5
# 模糊匹配最大候选起始位置数（限制搜索空间避免长文本 O(n^2)）
_MAX_FUZZY_START_POSITIONS = 300


def _build_full_text(words: list[WordTimestamp]) -> tuple[str, list[tuple[int, int, int]]]:
    """构建全文和字符位置索引

    Returns:
        (full_text, positions)
        positions[i] = (start_char, end_char, word_index)
    """
    full_text = ""
    positions: list[tuple[int, int, int]] = []
    for i, w in enumerate(words):
        start = len(full_text)
        full_text += w.word
        positions.append((start, len(full_text), i))
    return full_text, positions


def _char_pos_to_timestamp(
    query_start: int,
    query_end: int,
    words: list[WordTimestamp],
    positions: list[tuple[int, int, int]],
) -> dict[str, float]:
    """将字符偏移映射回时间戳"""
    if not words:
        return {"start": 0.0, "end": 0.0}
    start_word_idx = 0
    end_word_idx = len(words) - 1

    for pos_start, pos_end, w_idx in positions:
        if pos_start <= query_start < pos_end:
            start_word_idx = w_idx
        if pos_start < query_end <= pos_end:
            end_word_idx = w_idx

    return {
        "start": words[start_word_idx].start,
        "end": words[end_word_idx].end,
    }


def find_text_timestamp(
    query: str,
    words: list[WordTimestamp],
    score_cutoff: float = _DEFAULT_SCORE_CUTOFF,
) -> Optional[dict[str, float]]:
    """在 Whisper 词表中查找文字片段对应的时间范围

    策略：
    1. 优先精确匹配（快）
    2. 精确匹配失败则用模糊匹配滑动窗口

    Args:
        query: 要查找的文字片段
        words: Whisper 字级时间戳列表
        score_cutoff: 匹配得分阈值（0-100）

    Returns:
        {"start": 开始秒数, "end": 结束秒数} 或 None
    """
    if not query or not words:
        return None

    full_text, positions = _build_full_text(words)
    if not full_text:
        return None

    # Phase 1: 精确匹配
    exact_pos = full_text.find(query)
    if exact_pos >= 0:
        return _char_pos_to_timestamp(exact_pos, exact_pos + len(query), words, positions)

    # Phase 2: 模糊匹配 — 滑动窗口（限制搜索空间避免长文本 O(n^2) 性能问题）
    query_len = len(query)
    best_score = 0.0
    best_range: Optional[tuple[int, int]] = None
    candidates_checked = 0

    for start_char, _, word_start in positions:
        if candidates_checked >= _MAX_FUZZY_START_POSITIONS:
            break
        # 预筛：长查询的首字符不匹配大概率不是最优结果，跳过
        if query_len > 5 and full_text[start_char:start_char + 1] != query[0]:
            continue
        candidates_checked += 1

        # 从当前单词开始累积文字，窗口长度 ≈ query 长度
        for end_char, _, word_end in positions[word_start:]:
            segment = full_text[start_char:end_char]
            if not segment:
                continue
            # 窗口超过 query 长度 _WINDOW_LENGTH_MULTIPLIER 倍就停止扩展
            if len(segment) > query_len * _WINDOW_LENGTH_MULTIPLIER and word_end > word_start:
                break
            score = fuzz.ratio(query, segment)
            if score > best_score:
                best_score = score
                best_range = (word_start, word_end)

    if best_score >= score_cutoff and best_range is not None:
        start_idx, end_idx = best_range
        return {
            "start": words[start_idx].start,
            "end": words[end_idx].end,
        }

    return None


def match_boundary(
    boundary_text: str,
    words: list[WordTimestamp],
    direction: str = "start",
    score_cutoff: float = _DEFAULT_SCORE_CUTOFF,
) -> Optional[float]:
    """匹配分镜边界文字对应的时间点

    Args:
        boundary_text: 边界文字片段
        words: Whisper 字级时间戳列表
        direction: "start" 返回起始时间，"end" 返回结束时间
        score_cutoff: 匹配得分阈值

    Returns:
        时间点（秒）或 None
    """
    if direction not in ("start", "end"):
        raise ValueError("direction 必须是 'start' 或 'end'")

    result = find_text_timestamp(boundary_text, words, score_cutoff)
    if result is None:
        return None

    return result["start"] if direction == "start" else result["end"]
