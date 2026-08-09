from agent.chains import RobustScoreParser


def test_score_parser_clamps_and_tolerates_string_values():
    result = RobustScoreParser().parse(
        """{
          "score": "12",
          "max_score": "10",
          "score_breakdown": {
            "accuracy": "9", "completeness": 20,
            "depth": "bad", "clarity": 8.7
          },
          "hit_points": ["命中"], "missed_points": [],
          "feedback": "测试", "is_correct": true
        }"""
    )
    assert result.score == 10
    assert result.score_breakdown.accuracy == 9
    assert result.score_breakdown.completeness == 10
    assert result.score_breakdown.depth == 10
    assert result.score_breakdown.clarity == 8


def test_score_parser_returns_zero_for_empty_output():
    result = RobustScoreParser().parse("")
    assert result.score == 0
    assert result.is_correct is False
