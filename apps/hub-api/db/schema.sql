-- Presales Hub — PostgreSQL Schema
-- For local dev, the SQLAlchemy ORM creates equivalent tables in SQLite

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    sector TEXT,
    region TEXT,
    tier TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stakeholders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    role TEXT,
    bu TEXT,
    expertise JSONB DEFAULT '[]',
    current_workload INT DEFAULT 0,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    rfp_type TEXT,
    deal_value_cr NUMERIC(10,2),
    win_probability INT DEFAULT 50,
    stage TEXT DEFAULT 'intake',
    owner_id UUID REFERENCES stakeholders(id),
    deadline DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE CASCADE,
    stage TEXT DEFAULT 'intake',
    health_score INT DEFAULT 0,
    content JSONB DEFAULT '{}',
    version INT DEFAULT 1,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES proposals(id) ON DELETE CASCADE,
    stakeholder_id UUID REFERENCES stakeholders(id),
    role TEXT,
    bu TEXT,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    due_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending',
    notes TEXT
);

CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES proposals(id) ON DELETE CASCADE,
    approver_id UUID REFERENCES stakeholders(id),
    stage TEXT,
    order_index INT DEFAULT 0,
    parallel_group TEXT,
    status TEXT DEFAULT 'pending',
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sla_configs (
    stage TEXT PRIMARY KEY,
    hours_allowed INT NOT NULL,
    escalate_to_role TEXT
);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT,
    entity_id UUID,
    actor_id UUID REFERENCES stakeholders(id),
    action TEXT,
    from_state TEXT,
    to_state TEXT,
    metadata JSONB DEFAULT '{}',
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE activity_feed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES proposals(id) ON DELETE CASCADE,
    actor_name TEXT,
    action_type TEXT,
    description TEXT,
    is_alert BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sme_routing_rules (
    id SERIAL PRIMARY KEY,
    rfp_type TEXT NOT NULL,
    required_expertise TEXT NOT NULL,
    bu TEXT,
    priority INT DEFAULT 1
);

-- SLA defaults
INSERT INTO sla_configs VALUES
    ('intake',            4,  'presales_lead'),
    ('qualification',    24,  'presales_lead'),
    ('sme_assignment',    8,  'presales_lead'),
    ('drafting',         72,  'solution_architect'),
    ('technical_review', 24,  'solution_architect'),
    ('security_review',  24,  'security_reviewer'),
    ('finance_review',   16,  'finance'),
    ('legal_review',     24,  'legal'),
    ('approval',          4,  'presales_lead'),
    ('submission',        2,  'presales_lead');

-- Indexes
CREATE INDEX idx_opportunities_stage    ON opportunities(stage);
CREATE INDEX idx_proposals_stage        ON proposals(stage);
CREATE INDEX idx_approvals_proposal     ON approvals(proposal_id);
CREATE INDEX idx_activity_proposal      ON activity_feed(proposal_id);
CREATE INDEX idx_activity_created       ON activity_feed(created_at DESC);
CREATE INDEX idx_audit_entity           ON audit_log(entity_id);
