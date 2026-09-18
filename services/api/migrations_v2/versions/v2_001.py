"""Frozen v2 initial schema; independent databases, no v1 migration."""
from alembic import context, op
revision = "v2_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    commerce = context.get_x_argument(as_dictionary=True).get("database") == "commerce"
    if commerce:
        op.execute('\nCREATE TABLE orders (\n\torder_no VARCHAR(64) NOT NULL, \n\tcustomer_id VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tpaid_fen INTEGER NOT NULL, \n\trefunded_fen INTEGER NOT NULL, \n\tpaid_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdelivered_at TIMESTAMP WITH TIME ZONE, \n\tpromised_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\ttracking_no VARCHAR(64), \n\tcarrier_events JSON NOT NULL, \n\tPRIMARY KEY (order_no)\n)\n\n')
        op.execute('\nCREATE TABLE business_results (\n\texecution_id VARCHAR(36) NOT NULL, \n\tentitlement_key VARCHAR(160) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\torder_no VARCHAR(64) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (execution_id), \n\tUNIQUE (entitlement_key), \n\tFOREIGN KEY(order_no) REFERENCES orders (order_no)\n)\n\n')
        op.execute('CREATE INDEX ix_business_results_order_no ON business_results (order_no)')
        op.execute('\nCREATE TABLE order_items (\n\tid VARCHAR(64) NOT NULL, \n\torder_no VARCHAR(64) NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tcategory VARCHAR(30) NOT NULL, \n\taftersales_type VARCHAR(30) NOT NULL, \n\tpaid_fen INTEGER NOT NULL, \n\trefunded_fen INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(order_no) REFERENCES orders (order_no)\n)\n\n')
        op.execute('CREATE INDEX ix_order_items_order_no ON order_items (order_no)')
        op.execute('\nCREATE TABLE tickets (\n\tid VARCHAR(36) NOT NULL, \n\texecution_id VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\torder_no VARCHAR(64) NOT NULL, \n\tresolution VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (execution_id), \n\tFOREIGN KEY(execution_id) REFERENCES business_results (execution_id)\n)\n\n')
    else:
        op.execute('\nCREATE TABLE budget_accounts (\n\tid VARCHAR(40) NOT NULL, \n\tcommitted_microyuan BIGINT NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n')
        op.execute('\nCREATE TABLE cases (\n\tid VARCHAR(36) NOT NULL, \n\towner VARCHAR(40) NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\torder_no VARCHAR(64), \n\titem_id VARCHAR(64), \n\tintent VARCHAR(40), \n\tgeneration INTEGER NOT NULL, \n\tcurrent_plan_id VARCHAR(36), \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\ttarget_reported_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)\n\n')
        op.execute('\nCREATE TABLE login_sessions (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\trole VARCHAR(20) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (token_hash)\n)\n\n')
        op.execute('\nCREATE TABLE model_calls (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36), \n\tprovider VARCHAR(30) NOT NULL, \n\tmodel VARCHAR(100) NOT NULL, \n\treserved_microyuan BIGINT NOT NULL, \n\tactual_microyuan BIGINT, \n\tusage JSON, \n\tpricing JSON NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\telapsed_ms INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n')
        op.execute('CREATE INDEX ix_model_calls_case_id ON model_calls (case_id)')
        op.execute('\nCREATE TABLE policies (\n\tid VARCHAR(80) NOT NULL, \n\tversion VARCHAR(20) NOT NULL, \n\tintent VARCHAR(40) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\teffective_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\teffective_to TIMESTAMP WITH TIME ZONE, \n\trules JSON NOT NULL, \n\tcontent TEXT NOT NULL, \n\tchecksum VARCHAR(64) NOT NULL, \n\tembedding VECTOR(512), \n\tembedding_model VARCHAR(200), \n\tPRIMARY KEY (id)\n)\n\n')
        op.execute('CREATE INDEX ix_policies_intent ON policies (intent)')
        op.execute('\nCREATE TABLE request_records (\n\tkey VARCHAR(200) NOT NULL, \n\tchecksum VARCHAR(64) NOT NULL, \n\tresponse JSON NOT NULL, \n\tPRIMARY KEY (key)\n)\n\n')
        op.execute('\nCREATE TABLE case_messages (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\trole VARCHAR(20) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tgeneration INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id)\n)\n\n')
        op.execute('CREATE INDEX ix_case_messages_case_id ON case_messages (case_id)')
        op.execute('\nCREATE TABLE events (\n\tid BIGSERIAL NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(60) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id)\n)\n\n')
        op.execute('CREATE INDEX ix_events_case_id ON events (case_id)')
        op.execute('\nCREATE TABLE evidence_snapshots (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tgeneration INTEGER NOT NULL, \n\ttool VARCHAR(60) NOT NULL, \n\targuments JSON NOT NULL, \n\tpayload JSON NOT NULL, \n\tchecksum VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id)\n)\n\n')
        op.execute('CREATE INDEX ix_evidence_snapshots_case_id ON evidence_snapshots (case_id)')
        op.execute('\nCREATE TABLE jobs (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(20) NOT NULL, \n\treference_id VARCHAR(36) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tattempts INTEGER NOT NULL, \n\tavailable_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\towner_token VARCHAR(36), \n\terror TEXT, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id), \n\tUNIQUE (reference_id)\n)\n\n')
        op.execute('CREATE INDEX ix_jobs_status ON jobs (status)')
        op.execute('CREATE INDEX ix_jobs_case_id ON jobs (case_id)')
        op.execute('\nCREATE TABLE plan_versions (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tgeneration INTEGER NOT NULL, \n\tpayload JSON NOT NULL, \n\tchecksum VARCHAR(64) NOT NULL, \n\trequires_approval BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id)\n)\n\n')
        op.execute('CREATE INDEX ix_plan_versions_case_id ON plan_versions (case_id)')
        op.execute('\nCREATE TABLE approval_decisions (\n\tid VARCHAR(36) NOT NULL, \n\tplan_id VARCHAR(36) NOT NULL, \n\tplan_checksum VARCHAR(64) NOT NULL, \n\treviewer VARCHAR(40) NOT NULL, \n\tapproved BOOLEAN NOT NULL, \n\tcomment TEXT NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (plan_id), \n\tFOREIGN KEY(plan_id) REFERENCES plan_versions (id)\n)\n\n')
        op.execute('\nCREATE TABLE executions (\n\tid VARCHAR(36) NOT NULL, \n\tplan_id VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tplan_checksum VARCHAR(64) NOT NULL, \n\tconfirmed_by VARCHAR(40) NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\tresult JSON, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (plan_id), \n\tFOREIGN KEY(plan_id) REFERENCES plan_versions (id), \n\tFOREIGN KEY(case_id) REFERENCES cases (id)\n)\n\n')
        op.execute('CREATE INDEX ix_executions_case_id ON executions (case_id)')

def downgrade():
    raise RuntimeError("v2 database destruction is not an automatic downgrade")
