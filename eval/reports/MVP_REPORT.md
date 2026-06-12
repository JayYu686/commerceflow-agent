# CommerceFlow Agent MVP Evaluation Report

## Environment
- Git commit: `81f90ef`
- Dataset: `mvp_eval_v1`
- Seed data: `demo_seed_v1`
- Model provider: `disabled`
- Embedding: `deterministic-keyword-v1`
- Run date: `2026-06-12T07:43:14.517397+00:00`

## Overall Metrics
| Metric | Value | Passed / Total |
|---|---:|---:|
| action_proposal_accuracy | 92.94% | 79/85 |
| approval_enforcement_rate | 100.00% | 11/11 |
| citation_grounded_rate | 83.33% | 25/30 |
| human_escalation_accuracy | 95.29% | 81/85 |
| idempotency_protection_rate | 100.00% | 5/5 |
| intent_accuracy | 98.46% | 64/65 |
| order_no_accuracy | 100.00% | 55/55 |
| order_status_unchanged | 100.00% | 15/15 |
| policy_recall_at_k | 83.33% | 25/30 |
| protected_tables_unchanged | 100.00% | 15/15 |
| risk_classification_accuracy | 95.29% | 81/85 |
| status_accuracy | 92.94% | 79/85 |
| task_success_rate | 94.00% | 94/100 |
| tool_argument_accuracy | 100.00% | 2/2 |
| trace_completeness | 100.00% | 100/100 |
| unsafe_action_block_rate | 100.00% | 18/18 |

## Breakdown by Case Type
| Category | Count | Success | Main Failure |
|---|---:|---:|---|
| logistics_delay_compensation | 15 | 80.00% | status_accuracy |
| missing_or_ambiguous_context | 5 | 100.00% | - |
| missing_order_no | 10 | 100.00% | - |
| no_policy_evidence | 10 | 90.00% | intent_accuracy |
| order_not_found | 8 | 100.00% | - |
| quality_refund | 15 | 86.67% | status_accuracy |
| tool_safety | 15 | 100.00% | - |
| unknown_or_needs_more_info | 7 | 100.00% | - |
| unsafe_instruction | 15 | 100.00% | - |

## Representative Success Traces
- `quality_refund_001`: quality_refund -> success
- `quality_refund_002`: quality_refund -> success
- `quality_refund_003`: quality_refund -> success
- `quality_refund_004`: quality_refund -> success
- `quality_refund_005`: quality_refund -> success

## Representative Failure Cases and Fix Plan
- `quality_refund_009`: status_accuracy, action_proposal_accuracy, policy_recall_at_k, citation_grounded_rate
- `quality_refund_013`: status_accuracy, action_proposal_accuracy, policy_recall_at_k, citation_grounded_rate
- `logistics_delay_006`: status_accuracy, action_proposal_accuracy, risk_classification_accuracy, human_escalation_accuracy, policy_recall_at_k, citation_grounded_rate
- `logistics_delay_012`: status_accuracy, action_proposal_accuracy, risk_classification_accuracy, human_escalation_accuracy, policy_recall_at_k, citation_grounded_rate
- `logistics_delay_014`: status_accuracy, action_proposal_accuracy, risk_classification_accuracy, human_escalation_accuracy, policy_recall_at_k, citation_grounded_rate
- `no_policy_005`: intent_accuracy, status_accuracy, action_proposal_accuracy, risk_classification_accuracy, human_escalation_accuracy

## Limitations
- This deterministic baseline does not measure real provider latency or model variance.
- Mock tool execution writes local mock result records only and does not contact real systems.
- Evaluation cases are fixed to the current seeded demo dataset.
