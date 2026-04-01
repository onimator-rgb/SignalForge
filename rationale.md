# Rationale — marketpulse-task-2026-04-01-0001

## 1. Task Summary
Add sentiment score signal to the recommendation scoring engine as an 11th signal with weight 0.08, integrating the existing sentiment classifier output.

## 2. Goal
Recommendations incorporate sentiment data from news headlines, improving signal coverage from 10 to 11 factors.

## 3. Approach
- Added `score_sentiment()` function that maps classifier output [-1, 1] directly as signal score
- Redistributed existing weights by reducing each by 0.008 to free 0.08 for sentiment
- Added optional `sentiment_score` parameter to `compute_recommendation()` for backward compatibility

## 4. Files Changed
| File | Change |
|------|--------|
| `backend/app/recommendations/scoring.py` | Added sentiment signal, updated weights, bumped to v4 |
| `backend/tests/test_sentiment_scoring.py` | 9 new tests for sentiment signal |
| `backend/tests/test_mtf_scoring.py` | Updated assertions for 11 signals and new weights |
| `backend/tests/test_stochrsi.py` | Updated weight count assertion from 10 to 11 |

## 5. Weight Redistribution
Each existing signal reduced by 0.008. New total: 0.920 (existing) + 0.08 (sentiment) = 1.00.

## 6. Backward Compatibility
`sentiment_score` defaults to `None`, which yields a neutral 0.0 score. Existing callers are unaffected.

## 7. Tests
- 9 new tests covering: None input, positive/negative/neutral scores, clamping, weight sum, composite comparison, backward compatibility
- All 42 affected tests pass

## 8. Static Analysis
mypy passes with no errors on `scoring.py`.

## 9. Risks
Weight redistribution changes existing signal weights by ~0.008 each — marginal impact on borderline recommendations.

## 10. Security
No secrets, no external API calls, no broker SDK usage. Paper-trading only.

## 11. Limitations
Sentiment signal depends on upstream headline fetcher and classifier. When no headlines are available, signal defaults to neutral (0.0).

## 12. Next Steps
Service layer (`service.py`) can be updated to pass `sentiment_score` from the classifier when computing recommendations.
