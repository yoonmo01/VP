-- 스키마/확장 -----------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS vp;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 전술(택틱) 코드 마스터 -------------------------------------------------------
CREATE TABLE IF NOT EXISTS vp.tactic (
  code        TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT
);

-- 시뮬레이션/라운드/에이전트 ---------------------------------------------------
CREATE TABLE IF NOT EXISTS vp.simulation (
  id           BIGSERIAL PRIMARY KEY,
  label        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vp.round (
  id            BIGSERIAL PRIMARY KEY,
  simulation_id BIGINT NOT NULL REFERENCES vp.simulation(id) ON DELETE CASCADE,
  round_idx     INTEGER NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (simulation_id, round_idx)
);

CREATE TABLE IF NOT EXISTS vp.agent (
  id            BIGSERIAL PRIMARY KEY,
  simulation_id BIGINT REFERENCES vp.simulation(id) ON DELETE SET NULL,
  role          TEXT NOT NULL CHECK (role IN ('ATTACKER','VICTIM','POLICE','ADMIN')),
  persona       JSONB NOT NULL DEFAULT '{}',
  risk_score    NUMERIC(5,2),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 대화/메시지/판정 -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vp.convo (
  id            BIGSERIAL PRIMARY KEY,
  round_id      BIGINT NOT NULL REFERENCES vp.round(id) ON DELETE CASCADE,
  attacker_id   BIGINT REFERENCES vp.agent(id) ON DELETE SET NULL,
  victim_id     BIGINT REFERENCES vp.agent(id) ON DELETE SET NULL,
  transcript    TEXT NOT NULL,
  meta          JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vp.convo_message (
  id            BIGSERIAL PRIMARY KEY,
  convo_id      BIGINT NOT NULL REFERENCES vp.convo(id) ON DELETE CASCADE,
  turn_idx      INTEGER NOT NULL,
  speaker_role  TEXT NOT NULL CHECK (speaker_role IN ('ATTACKER','VICTIM','SYSTEM')),
  content       TEXT NOT NULL,
  meta          JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (convo_id, turn_idx)
);

CREATE TABLE IF NOT EXISTS vp.outcome (
  convo_id     BIGINT PRIMARY KEY REFERENCES vp.convo(id) ON DELETE CASCADE,
  is_phished   BOOLEAN NOT NULL,
  confidence   NUMERIC(4,3),
  reason       TEXT,
  decided_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vp.convo_tactic (
  convo_id    BIGINT NOT NULL REFERENCES vp.convo(id) ON DELETE CASCADE,
  tactic_code TEXT   NOT NULL REFERENCES vp.tactic(code) ON DELETE RESTRICT,
  score       NUMERIC(4,3) CHECK (score >= 0 AND score <= 1),
  PRIMARY KEY (convo_id, tactic_code)
);

-- 예방 교육 모듈(피해자용) -----------------------------------------------------
CREATE TABLE IF NOT EXISTS vp.prevention_module (
  id           BIGSERIAL PRIMARY KEY,
  tactic_code  TEXT REFERENCES vp.tactic(code) ON DELETE SET NULL,
  title        TEXT NOT NULL,
  summary_md   TEXT NOT NULL,
  script_md    TEXT NOT NULL,
  level        TEXT NOT NULL DEFAULT 'basic' CHECK (level IN ('basic','intermediate','advanced')),
  locale       TEXT NOT NULL DEFAULT 'ko',
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 공격 보강 모듈(연구/시뮬레이션용, 가상) -------------------------------------
CREATE TABLE IF NOT EXISTS vp.attack_module (
  id           BIGSERIAL PRIMARY KEY,
  tactic_code  TEXT,
  title        TEXT NOT NULL,
  playbook_md  TEXT NOT NULL,
  cues_md      TEXT NOT NULL,
  level        TEXT NOT NULL DEFAULT 'basic' CHECK (level IN ('basic','intermediate','advanced')),
  locale       TEXT NOT NULL DEFAULT 'ko',
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 가이던스 할당 기록(피해자/공격자 공용) -------------------------------------
CREATE TABLE IF NOT EXISTS vp.guidance_assignment (
  id           BIGSERIAL PRIMARY KEY,
  convo_id     BIGINT NOT NULL REFERENCES vp.convo(id) ON DELETE CASCADE,
  target_role  TEXT NOT NULL CHECK (target_role IN ('VICTIM','ATTACKER')),
  module_table TEXT NOT NULL CHECK (module_table IN ('prevention','attack')),
  module_id    BIGINT NOT NULL,
  notes        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 감사 로그 --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vp.audit_log (
  id           BIGSERIAL PRIMARY KEY,
  who          TEXT,
  action       TEXT NOT NULL,
  detail       JSONB NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 인덱스 ----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_convo_transcript_trgm ON vp.convo USING GIN (transcript gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_convo_round_id ON vp.convo(round_id);
CREATE INDEX IF NOT EXISTS idx_outcome_is_phished ON vp.outcome(is_phished);
CREATE INDEX IF NOT EXISTS idx_convo_tactic_code ON vp.convo_tactic(tactic_code);
CREATE INDEX IF NOT EXISTS idx_module_tactic_level_prev ON vp.prevention_module(tactic_code, level) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_module_tactic_level_attk ON vp.attack_module(tactic_code, level) WHERE is_active;

-- 뷰 --------------------------------------------------------------------------
CREATE OR REPLACE VIEW vp.v_latest_convos AS
SELECT c.id AS convo_id, r.simulation_id, r.round_idx,
       o.is_phished, o.confidence, c.created_at
FROM vp.convo c
LEFT JOIN vp.outcome o ON o.convo_id = c.id
JOIN vp.round r ON r.id = c.round_id;

-- === 인테이크(시뮬 로그 JSON) / 배치 / 맞춤형 예방 대책 ======================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 시뮬레이션 배치(한 피해자/시나리오로 5회 러닝 같은 묶음)
CREATE TABLE IF NOT EXISTS vp.sim_batch (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  label        TEXT,
  victim_ref   JSONB,       -- {id, name, meta, knowledge, traits}
  offender_ref JSONB,       -- {id, name, type, profile}
  scenario_ref JSONB,       -- {steps, purpose, ...}
  intended_runs INTEGER NOT NULL DEFAULT 5,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 개별 러닝(시뮬 1회) 인테이크 원본 저장
CREATE TABLE IF NOT EXISTS vp.sim_run_intake (
  id           BIGSERIAL PRIMARY KEY,
  batch_id     UUID REFERENCES vp.sim_batch(id) ON DELETE CASCADE,
  case_id      UUID,           -- 시뮬레이터가 준 case_id
  raw_json     JSONB NOT NULL, -- 네가 준 JSON 전체
  is_phished   BOOLEAN,        -- 에이전트 판단(또는 json에 있으면 그대로)
  tactic_code  TEXT,           -- 간단 규칙 추정(없어도 됨)
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sim_run_intake_batch ON vp.sim_run_intake(batch_id);
CREATE INDEX IF NOT EXISTS idx_sim_run_intake_case  ON vp.sim_run_intake(case_id);

-- 맞춤형 예방 대책 (배치 5회 끝난 후 생성)
CREATE TABLE IF NOT EXISTS vp.personalized_plan (
  id           BIGSERIAL PRIMARY KEY,
  batch_id     UUID REFERENCES vp.sim_batch(id) ON DELETE CASCADE,
  victim_ref   JSONB,
  offender_ref JSONB,
  scenario_ref JSONB,
  insights_md  TEXT NOT NULL,   -- 관찰/패턴/취약요인 요약
  plan_md      TEXT NOT NULL,   -- 맞춤형 예방 대책 (프론트로 보낼 본문)
  sources      JSONB DEFAULT '[]'::jsonb, -- 사용한 모듈/근거
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
