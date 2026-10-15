CREATE TABLE IF NOT EXISTS site_events (
    event_id uuid PRIMARY KEY,
    session_id varchar(100) NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    name varchar(64) NOT NULL,
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    text text NOT NULL,
    status text NOT NULL CHECK (status IN ('recorded', 'pending', 'sending', 'sent')),
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_token uuid,
    message_id bigint,
    sent_at timestamptz
);
CREATE INDEX IF NOT EXISTS site_events_outbox ON site_events (available_at, received_at)
    WHERE status IN ('pending', 'sending');
CREATE INDEX IF NOT EXISTS site_events_session ON site_events (session_id, sequence);
