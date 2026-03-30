-- Session Co-Pilot: session history table
-- Run this once in your Supabase SQL editor.
-- Safe to re-run (uses IF NOT EXISTS throughout).

create table if not exists session_history (
    id              uuid            primary key,
    user_id         text,                               -- nullable: anonymous sessions allowed in V1
    session_brief   text            not null,
    target_artist   text,
    mood            text,
    detected_key    text,
    detected_bpm    integer,
    response        jsonb           not null,           -- full CopilotResponse payload
    provider        text            not null default 'mock',
    created_at      timestamptz     not null default now()
);

-- Lookup by user (history tab, future feature)
create index if not exists session_history_user_id_idx
    on session_history (user_id);

-- Lookup by recency
create index if not exists session_history_created_at_idx
    on session_history (created_at desc);
