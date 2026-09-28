-- tailscaletest internal-db seed schema.
-- Only here to prove that the connection is real; no production-shaped data.

CREATE TABLE IF NOT EXISTS people (
    id    SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    role  TEXT NOT NULL
);

INSERT INTO people (email, role) VALUES
    ('ada@tailscaletest.example',   'engineer'),
    ('linus@tailscaletest.example', 'engineer'),
    ('eve@tailscaletest.example',   'untrusted');